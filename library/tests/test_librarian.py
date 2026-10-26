import json
from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from library import librarian
from library.gemini import QuotaExceeded
from library.models import LibrarianAnswer

from .factories import make_book, make_user
from .test_embeddings import axis

DRACULA_SUMMARY = ("Jonathan Harker travels to Transylvania to help Count Dracula buy a house in England, "
                   "and finds himself a prisoner in the castle. " + "More of the story. " * 60)


def text(*picks):
    """The JSON text a pass answers with. Each pick is (book_id, reason) or (book_id, reason, quote)."""
    keys = ("book_id", "reason", "quote")
    return json.dumps({"picks": [dict(zip(keys, (str(p[0]),) + tuple(p[1:]))) for p in picks]})


def gemini_says(*picks):
    """What Gemini's generateContent returns when a pass answers with these picks."""
    return {"candidates": [{"content": {"parts": [{"text": text(*picks)}]}}]}


class LibrarianTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.dracula = make_book(title="Dracula", description=DRACULA_SUMMARY)
        self.quijote = make_book(title="Don Quijote", description="A gentleman reads so many romances of chivalry that he decides to become a knight-errant.")
        self.platero = make_book(title="Platero y yo", description="A poet walks the Andalusian countryside with his donkey Platero.")
        for i, book in enumerate([self.dracula, self.quijote, self.platero]):
            book.embedding = axis(i)
            book.save()
        self.books = [self.dracula, self.quijote, self.platero]


class RequestTests(LibrarianTestCase):
    def schema_item(self, body):
        return body["generationConfig"]["responseSchema"]["properties"]["picks"]["items"]

    def test_summary_pass_lists_summaries_and_asks_for_a_quote(self):
        body = librarian.summary_request("algo de miedo", self.books)
        item = self.schema_item(body)
        self.assertEqual(item["properties"]["book_id"]["enum"], [str(b.pk) for b in self.books])
        self.assertEqual(item["required"], ["book_id", "reason", "quote"])
        listing = body["contents"][0]["parts"][0]["text"]
        self.assertIn("Jonathan Harker travels", listing)
        self.assertLess(listing.count("More of the story."), 60)  # long summaries are cut

    def test_knowledge_pass_lists_titles_only_and_asks_for_no_quote(self):
        body = librarian.knowledge_request("algo de miedo", self.books)
        self.assertNotIn("quote", self.schema_item(body)["properties"])
        listing = body["contents"][0]["parts"][0]["text"]
        self.assertIn("Dracula", listing)
        self.assertNotIn("Jonathan Harker", listing)
        self.assertIn("what you know", body["systemInstruction"]["parts"][0]["text"])


class QuoteTests(SimpleTestCase):
    def test_a_word_for_word_excerpt_passes_give_or_take_case_spacing_and_marks(self):
        summary = "He finds himself a prisoner in the castle — and the Count’s guest."
        self.assertTrue(librarian.quote_in_summary("finds himself a prisoner in the castle", summary))
        self.assertTrue(librarian.quote_in_summary("“Finds  himself a PRISONER in the castle…”", summary))
        self.assertTrue(librarian.quote_in_summary("in the castle - and the Count's guest", summary))

    def test_a_paraphrase_or_a_scrap_does_not(self):
        summary = "He finds himself a prisoner in the castle."
        self.assertFalse(librarian.quote_in_summary("he is held captive in the castle", summary))
        self.assertFalse(librarian.quote_in_summary("the castle", summary))


class CheckTests(LibrarianTestCase):
    def test_summary_picks_need_a_quote_from_their_own_summary(self):
        picks, dropped = librarian.check_summary_picks(text(
            (self.dracula.pk, "Miedo clásico.", "finds himself a prisoner in the castle"),
            (self.quijote.pk, "Not backed.", "finds himself a prisoner in the castle"),   # Dracula's line, not his
            (self.platero.pk, "Invented line.", "a donkey who fights vampires at night")), self.books)
        self.assertEqual([b for b, _, _ in picks], [self.dracula])
        self.assertEqual(dropped, 2)

    def test_invented_ids_empty_reasons_repeats_and_extras_are_dropped(self):
        extra = make_book(title="Extra")
        picks, dropped = librarian.check_knowledge_picks(text(
            (99999, "Not listed."), (self.quijote.pk, "  "), (self.dracula.pk, "Yes."), (self.dracula.pk, "Again."),
            (self.platero.pk, "Two."), (extra.pk, "Three."), (self.quijote.pk, "Four.")), self.books + [extra])
        self.assertEqual([b for b, _ in picks], [self.dracula, self.platero, extra])
        self.assertEqual(dropped, 4)

    def test_an_answer_that_is_not_the_json_asked_for_passes_nothing(self):
        for answer in ("Dracula, obviously.", "[]", '{"picks": "Dracula"}'):
            with self.subTest(answer=answer):
                self.assertEqual(librarian.check_summary_picks(answer, self.books), ([], 1))

    def test_cards_put_what_both_passes_agree_on_first(self):
        summary = [(self.platero, "S1", "q1"), (self.dracula, "S2", "q2")]
        knowledge = [(self.dracula, "K1"), (self.quijote, "K2")]
        cards = librarian.cards(summary, knowledge)
        self.assertEqual([c["book"] for c in cards], [self.dracula, self.platero, self.quijote])
        self.assertEqual((cards[0]["reason"], cards[0]["knowledge"]), ("S2", "K1"))
        self.assertIsNone(cards[2]["quote"])


@override_settings(GEMINI_API_KEY="site-key")
class SiteKeyTests(LibrarianTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(make_user())
        self.url = reverse("librarian")

    def ask(self, *answers):
        with mock.patch("library.views.query_vector", return_value=axis(0)), \
                mock.patch("library.views.call", side_effect=list(answers)) as fake:
            return self.client.post(self.url, {"question": "algo de miedo"}), fake

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_both_passes_are_shown_labelled_and_logged(self):
        response, fake = self.ask(
            gemini_says((self.dracula.pk, "Un conde vampiro.", "finds himself a prisoner in the castle"),
                        (self.quijote.pk, "Bad quote.", "windmills everywhere in this summary")),
            gemini_says((self.dracula.pk, "Bram Stoker's epistolary novel."), (424242, "Invented.")))
        self.assertEqual(fake.call_count, 2)
        self.assertContains(response, "From its summary")
        self.assertContains(response, "“finds himself a prisoner in the castle”")
        self.assertContains(response, "What the librarian also knows")
        self.assertContains(response, "Bram Stoker&#x27;s epistolary novel.")
        self.assertNotContains(response, "Invented.")
        self.assertContains(response, "The check removed 2 suggestions")
        log = LibrarianAnswer.objects.get()
        self.assertEqual((log.picks, log.dropped, log.knowledge_picks, log.knowledge_dropped, log.key),
                         ([self.dracula.pk], 1, [self.dracula.pk], 1, "site"))

    def test_if_the_knowledge_pass_fails_the_summaries_still_answer(self):
        response, _ = self.ask(gemini_says((self.dracula.pk, "Miedo.", "finds himself a prisoner in the castle")),
                               QuotaExceeded("busy"))
        self.assertContains(response, "Miedo.")
        self.assertContains(response, "could not run this time")
        self.assertTrue(LibrarianAnswer.objects.get().knowledge_failed)

    def test_nothing_fits(self):
        response, _ = self.ask(gemini_says(), gemini_says())
        self.assertContains(response, "Nothing in the catalog fits")

    @override_settings(LIBRARIAN_QUESTIONS_PER_READER_PER_DAY=1)
    def test_daily_cap_stops_before_calling_gemini(self):
        self.ask(gemini_says(), gemini_says())
        response, fake = self.ask(gemini_says(), gemini_says())
        fake.assert_not_called()
        self.assertContains(response, "used up")

    def test_provider_error_on_the_first_pass_is_explained(self):
        response, _ = self.ask(QuotaExceeded("busy"))
        self.assertContains(response, "cannot answer right now")
        self.assertFalse(LibrarianAnswer.objects.exists())


@override_settings(GEMINI_API_KEY="")
class ReaderKeyTests(LibrarianTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(make_user())

    def post_json(self, name, data):
        return self.client.post(reverse(name), json.dumps(data), content_type="application/json")

    def candidates(self, vector=None):
        return self.post_json("librarian_candidates", {"question": "algo de miedo", "vector": vector or axis(0)})

    def test_without_a_site_key_the_form_does_not_post(self):
        self.assertEqual(self.client.post(reverse("librarian"), {"question": "algo"}).status_code, 400)
        self.assertContains(self.client.get(reverse("librarian")), 'data-site-key="false"')

    def test_candidates_bring_both_requests_closest_first(self):
        data = self.candidates().json()
        for name in ("summary_body", "knowledge_body"):
            enum = data[name]["generationConfig"]["responseSchema"]["properties"]["picks"]["items"]["properties"]["book_id"]["enum"]
            self.assertEqual(enum[0], str(self.dracula.pk))
        self.assertEqual(data["model"], "gemini-3.5-flash-lite")

    def test_a_bad_vector_is_refused(self):
        for vector in ([0.1, 0.2], ["x"] * 768, "nope"):
            with self.subTest(vector=str(vector)[:20]):
                self.assertEqual(self.post_json("librarian_candidates", {"question": "q", "vector": vector}).status_code, 400)

    def test_answers_are_checked_against_the_same_lists_once(self):
        token = self.candidates().json()["token"]
        payload = {"token": token,
                   "summary_text": text((self.dracula.pk, "Castillo.", "finds himself a prisoner in the castle")),
                   "knowledge_text": text((self.quijote.pk, "Molinos."), (31337, "Invented."))}
        html = self.post_json("librarian_answer", payload).json()["html"]
        self.assertIn("Castillo.", html)
        self.assertIn("Molinos.", html)
        self.assertNotIn("Invented.", html)
        log = LibrarianAnswer.objects.get()
        self.assertEqual((log.picks, log.knowledge_picks, log.knowledge_dropped, log.key),
                         ([self.dracula.pk], [self.quijote.pk], 1, "reader"))
        self.assertEqual(self.post_json("librarian_answer", payload).status_code, 400)

    def test_a_failed_knowledge_pass_in_the_browser_is_recorded(self):
        token = self.candidates().json()["token"]
        self.post_json("librarian_answer", {"token": token, "summary_text": text(), "knowledge_text": None})
        self.assertTrue(LibrarianAnswer.objects.get().knowledge_failed)

    def test_another_readers_token_is_refused(self):
        token = self.candidates().json()["token"]
        self.client.force_login(make_user("someone-else"))
        self.assertEqual(self.post_json("librarian_answer", {"token": token, "summary_text": "{}"}).status_code, 400)

    def test_ai_key_page_never_posts_the_key(self):
        response = self.client.get(reverse("ai_key"))
        self.assertContains(response, 'id="ai-key-form"')
        self.assertNotContains(response, 'method="post"')
