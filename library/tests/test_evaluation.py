import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from library.evaluation import drop_reasons, evaluate
from library.gemini import QuotaExceeded

from .factories import make_book
from .test_embeddings import axis
from .test_librarian import gemini_says


class EvaluationTests(TestCase):
    def setUp(self):
        self.dracula = make_book(title="Dracula", gutenberg_id=345,
                                 description="Jonathan Harker finds himself a prisoner in the castle of the Count.")
        self.quijote = make_book(title="Don Quijote", gutenberg_id=2000,
                                 description="A gentleman reads so many romances of chivalry that he becomes a knight-errant.")
        for i, book in enumerate([self.dracula, self.quijote]):
            book.embedding = axis(i)
            book.save()
        self.questions = [
            {"question": "vampiros", "language": "es", "expected": [345]},
            {"question": "molinos", "language": "es", "expected": [2000, 99999]},
            {"question": "programar en Python", "language": "es", "expected": []},
        ]

    def run_eval(self, answers):
        with mock.patch("library.evaluation.embed", return_value=[axis(0), axis(0), axis(1)]), \
                mock.patch("library.evaluation.call", side_effect=answers), \
                mock.patch("library.evaluation.time.sleep"):
            return evaluate(self.questions, log=lambda *_: None)

    def test_totals(self):
        quote = "finds himself a prisoner in the castle"
        results, totals = self.run_eval([
            gemini_says((self.dracula.pk, "Miedo.", quote)), gemini_says((self.dracula.pk, "Stoker.")),
            gemini_says((self.dracula.pk, "Wrong book.", quote)), gemini_says((self.quijote.pk, "Cervantes.")),
            gemini_says((self.quijote.pk, "Nothing fits, but...", "not in any summary at all, really")), gemini_says(),
        ])
        self.assertEqual(results[1]["missing_from_catalog"], [99999])
        self.assertEqual(totals["search_hit_at_5"]["hits"], 2)
        self.assertEqual(results[1]["first_expected_rank"], 2)
        self.assertEqual(totals["summary_pass_hit"]["hits"], 1)
        self.assertEqual(totals["knowledge_pass_hit"]["hits"], 2)
        self.assertEqual(totals["knowledge_only_hit"], 1)
        self.assertEqual(totals["summary_pass_abstained"]["hits"], 1)  # its only pick had a quote from nowhere
        self.assertEqual(totals["knowledge_pass_abstained"]["hits"], 1)
        self.assertEqual(totals["quotes_checked"], {"proposed": 3, "quote_not_in_summary": 1, "passed_rate": 0.667})

    def test_a_rate_limit_waits_and_tries_again(self):
        answers = [QuotaExceeded("busy"), gemini_says(), gemini_says(), gemini_says(), gemini_says(), gemini_says(), gemini_says()]
        results, _ = self.run_eval(answers)
        self.assertEqual(len(results), 3)

    def test_drop_reasons(self):
        books = [self.dracula, self.quijote]
        text = json.dumps({"picks": [
            {"book_id": "424242", "reason": "x", "quote": "y"},
            {"book_id": str(self.dracula.pk), "reason": "", "quote": "finds himself a prisoner in the castle"},
            {"book_id": str(self.quijote.pk), "reason": "ok", "quote": "a sentence that is not in the summary"},
            {"book_id": str(self.dracula.pk), "reason": "ok", "quote": "finds himself a prisoner in the castle"},
        ]})
        self.assertEqual(drop_reasons(text, books, with_quote=True),
                         {"not_listed": 1, "no_reason": 1, "quote_not_in_summary": 1})
        self.assertEqual(drop_reasons("not json", books, with_quote=True), {"not_json": 1})


class EvaluateCommandTests(TestCase):
    def test_writes_the_run_named_after_its_question_set_with_totals_by_kind(self):
        book = make_book(title="Dracula", gutenberg_id=345)
        book.embedding = axis(0)
        book.save()
        with tempfile.TemporaryDirectory() as tmp:
            questions = Path(tmp) / "questions_hard.json"
            questions.write_text(json.dumps({"questions": [
                {"question": "vampiros", "language": "es", "kind": "trap", "expected": [345]},
                {"question": "Python", "language": "es", "kind": "mood", "expected": []}]}), encoding="utf-8")
            with mock.patch("library.management.commands.evaluate.EVAL", Path(tmp)), \
                    mock.patch("library.evaluation.embed", return_value=[axis(0), axis(1)]):
                call_command("evaluate", "--retrieval-only", "--questions", str(questions), stdout=StringIO())
            written = list((Path(tmp) / "results").glob("*-hard-retrieval.json"))
            self.assertEqual(len(written), 1)
            run = json.loads(written[0].read_text(encoding="utf-8"))
            self.assertEqual(sorted(run["totals_by_kind"]), ["mood", "trap"])
            self.assertEqual(run["totals_by_kind"]["trap"]["search_hit_at_5"]["hits"], 1)
