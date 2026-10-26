import json
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from library import librarian
from library.gemini import QuotaExceeded
from library.models import LibrarianAnswer

from .factories import make_book, make_user
from .test_embeddings import axis


def model_says(*picks):
    """What Gemini's generateContent returns when the model picks these (book_id, reason) pairs."""
    text = json.dumps({"picks": [{"book_id": str(i), "reason": r} for i, r in picks]})
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


class LibrarianTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.dracula = make_book(title="Dracula", description="A vampire count. " * 100)
        self.quijote = make_book(title="Don Quijote")
        self.platero = make_book(title="Platero y yo")
        for i, book in enumerate([self.dracula, self.quijote, self.platero]):
            book.embedding = axis(i)
            book.save()
        self.books = [self.dracula, self.quijote, self.platero]


class RequestBodyTests(LibrarianTestCase):
    def test_the_answer_can_only_name_listed_books(self):
        body = librarian.request_body("algo de miedo", self.books)
        item = body["generationConfig"]["responseSchema"]["properties"]["picks"]["items"]
        self.assertEqual(item["properties"]["book_id"]["enum"], [str(b.pk) for b in self.books])
        self.assertIn("only from the books listed", body["systemInstruction"]["parts"][0]["text"])

    def test_long_summaries_are_cut(self):
        text = librarian.request_body("q", self.books)["contents"][0]["parts"][0]["text"]
        self.assertLess(text.count("A vampire count."), 100)
        self.assertIn("…", text)


class CheckPicksTests(LibrarianTestCase):
    def check(self, *picks):
        text = model_says(*picks)["candidates"][0]["content"]["parts"][0]["text"]
        return librarian.check_picks(text, self.books)

    def test_listed_books_with_a_reason_pass(self):
        picks, dropped = self.check((self.dracula.pk, "Miedo clásico."))
        self.assertEqual(picks, [(self.dracula, "Miedo clásico.")])
        self.assertEqual(dropped, 0)

    def test_invented_ids_empty_reasons_and_repeats_are_dropped(self):
        picks, dropped = self.check((99999, "Not in the list."), (self.quijote.pk, "  "),
                                    (self.dracula.pk, "Yes."), (self.dracula.pk, "Again."))
        self.assertEqual([b for b, _ in picks], [self.dracula])
        self.assertEqual(dropped, 3)

    def test_never_more_than_three(self):
        extra = make_book(title="Extra")
        picks, dropped = librarian.check_picks(
            json.dumps({"picks": [{"book_id": str(b.pk), "reason": "ok"} for b in self.books + [extra]]}),
            self.books + [extra])
        self.assertEqual((len(picks), dropped), (3, 1))

    def test_an_answer_that_is_not_the_json_asked_for_passes_nothing(self):
        for text in ("Dracula, obviously.", "[]", '{"picks": "Dracula"}'):
            with self.subTest(text=text):
                self.assertEqual(librarian.check_picks(text, self.books), ([], 1))


@override_settings(GEMINI_API_KEY="site-key")
class SiteKeyTests(LibrarianTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(make_user())
        self.url = reverse("librarian")

    def ask(self, model_answer, question="algo de miedo"):
        with mock.patch("library.views.query_vector", return_value=axis(0)), \
                mock.patch("library.views.call", return_value=model_answer) as fake:
            return self.client.post(self.url, {"question": question}), fake

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_checked_picks_are_shown_and_logged(self):
        response, fake = self.ask(model_says((self.dracula.pk, "Un conde vampiro."), (424242, "Invented.")))
        self.assertContains(response, "Un conde vampiro.")
        self.assertNotContains(response, "Invented.")
        self.assertContains(response, "The check removed 1 suggestion")
        log = LibrarianAnswer.objects.get()
        self.assertEqual((log.picks, log.dropped, log.key), ([self.dracula.pk], 1, "site"))
        self.assertEqual(fake.call_args.args[1], "generateContent")

    def test_nothing_fits(self):
        response, _ = self.ask(model_says())
        self.assertContains(response, "Nothing in the catalog fits")

    @override_settings(LIBRARIAN_QUESTIONS_PER_READER_PER_DAY=1)
    def test_daily_cap_stops_before_calling_gemini(self):
        self.ask(model_says((self.dracula.pk, "Uno.")))
        response, fake = self.ask(model_says((self.dracula.pk, "Dos.")))
        fake.assert_not_called()
        self.assertContains(response, "used up")

    def test_provider_error_is_explained(self):
        with mock.patch("library.views.query_vector", return_value=axis(0)), \
                mock.patch("library.views.call", side_effect=QuotaExceeded("busy")):
            response = self.client.post(self.url, {"question": "algo"})
        self.assertContains(response, "cannot answer right now")
        self.assertFalse(LibrarianAnswer.objects.exists())


@override_settings(GEMINI_API_KEY="")
class ReaderKeyTests(LibrarianTestCase):
    def setUp(self):
        super().setUp()
        self.reader = make_user()
        self.client.force_login(self.reader)

    def post_json(self, name, data):
        return self.client.post(reverse(name), json.dumps(data), content_type="application/json")

    def candidates(self, vector=None):
        return self.post_json("librarian_candidates", {"question": "algo de miedo", "vector": vector or axis(0)})

    def test_without_a_site_key_the_form_does_not_post(self):
        self.assertEqual(self.client.post(reverse("librarian"), {"question": "algo"}).status_code, 400)
        self.assertContains(self.client.get(reverse("librarian")), 'data-site-key="false"')

    def test_candidates_come_closest_first_with_a_closed_request(self):
        data = self.candidates().json()
        enum = data["body"]["generationConfig"]["responseSchema"]["properties"]["picks"]["items"]["properties"]["book_id"]["enum"]
        self.assertEqual(enum[0], str(self.dracula.pk))
        self.assertEqual(data["model"], "gemini-3.5-flash-lite")

    def test_a_bad_vector_is_refused(self):
        for vector in ([0.1, 0.2], ["x"] * 768, "nope"):
            with self.subTest(vector=str(vector)[:20]):
                self.assertEqual(self.post_json("librarian_candidates", {"question": "q", "vector": vector}).status_code, 400)

    def test_the_answer_is_checked_against_the_same_list_once(self):
        token = self.candidates().json()["token"]
        text = model_says((self.quijote.pk, "Molinos."), (31337, "Invented."))["candidates"][0]["content"]["parts"][0]["text"]
        response = self.post_json("librarian_answer", {"token": token, "text": text})
        self.assertIn("Molinos.", response.json()["html"])
        self.assertNotIn("Invented.", response.json()["html"])
        log = LibrarianAnswer.objects.get()
        self.assertEqual((log.picks, log.dropped, log.key), ([self.quijote.pk], 1, "reader"))
        self.assertEqual(self.post_json("librarian_answer", {"token": token, "text": text}).status_code, 400)

    def test_another_readers_token_is_refused(self):
        token = self.candidates().json()["token"]
        self.client.force_login(make_user("someone-else"))
        self.assertEqual(self.post_json("librarian_answer", {"token": token, "text": "{}"}).status_code, 400)

    def test_ai_key_page_never_posts_the_key(self):
        response = self.client.get(reverse("ai_key"))
        self.assertContains(response, 'id="ai-key-form"')
        self.assertNotContains(response, 'method="post"')
