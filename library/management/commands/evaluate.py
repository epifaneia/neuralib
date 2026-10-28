import json
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from library import librarian
from library.evaluation import evaluate, totals as totals_of

EVAL = Path(settings.BASE_DIR) / "eval"


class Command(BaseCommand):
    help = "Measure search and the librarian against eval/questions.json and write eval/results/."

    def add_arguments(self, parser):
        parser.add_argument("--retrieval-only", action="store_true", help="Only search: one embedding call in all.")
        parser.add_argument("--pause", type=float, default=4.0,
                            help="Seconds between librarian calls, to stay inside the free per-minute quota.")
        parser.add_argument("--questions", default=str(EVAL / "questions.json"))

    def handle(self, *args, retrieval_only=False, pause=4.0, questions=None, **options):
        source = Path(questions)
        questions = json.loads(source.read_text(encoding="utf-8"))["questions"]
        results, totals = evaluate(questions, retrieval_only=retrieval_only, pause=pause, log=self.stdout.write)
        run = {"date": datetime.now().isoformat(timespec="seconds"), "embedding_model": settings.EMBEDDING_MODEL,
               "librarian_model": None if retrieval_only else settings.LIBRARIAN_MODEL,
               "summary_candidates": librarian.SUMMARY_CANDIDATES, "knowledge_candidates": librarian.KNOWLEDGE_CANDIDATES,
               "totals": totals, "results": results}
        kinds = sorted({r["kind"] for r in results if r["kind"]})
        if kinds:
            run["totals_by_kind"] = {kind: totals_of([r for r in results if r["kind"] == kind]) for kind in kinds}
        out = EVAL / "results"
        out.mkdir(parents=True, exist_ok=True)
        name = source.stem.removeprefix("questions").strip("_") or "base"
        path = out / f"{run['date'].replace(':', '')}-{name}{'-retrieval' if retrieval_only else ''}.json"
        path.write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding="utf-8")
        self.stdout.write(json.dumps(run.get("totals_by_kind", totals), ensure_ascii=False, indent=1))
        self.stdout.write(f"Written to {path}")
