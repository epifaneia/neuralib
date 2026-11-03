import json
from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from library import librarian
from library.gemini import QuotaExceeded
from library.models import LibrarianAnswer

from .factories import make_book, make_user

DRACULA_SUMMARY = ("Jonathan Harker travels to Transylvania to help Count Dracula buy a house in England, "
                   "and finds himself a prisoner in the castle. " + "More of the story. " * 60)


def text(*picks):
    """The JSON text the model answers with. Each pick is (book_id, reason) or (book_id, reason, quote)."""
    keys = ("book_id", "reason", "quote")
    return json.dumps({"picks": [dict(zip(keys, (str(p[0]),) + tuple(p[1:]))) for p in picks]})


def gemini_says(*picks):
    """What Gemini's generateContent returns when the model answers with these picks."""
    return {"candidates": [{"content": {"parts": [{"text": text(*picks)}]}}]}


class LibrarianTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.dracula = make_book(title="Dracula", description=DRACULA_SUMMARY)
        self.quijote = make_book(title="Don Quijote", description="A gentleman reads so many romances of chivalry that he decides to become a knight-errant.")
        self.platero = make_book(title="Platero y yo", description="A poet walks the Andalusian countryside with his donkey Platero.")
        self.books = [self.dracula, self.quijote, self.platero]


class RequestTests(LibrarianTestCase):
    def test_the_whole_catalog_goes_in_and_its_ids_are_the_closed_list(self):
        body = librarian.request("algo de miedo", librarian.catalog())
        item = body["generationConfig"]["responseSchema"]["properties"]["picks"]["items"]
        self.assertEqual(item["properties"]["book_id"]["enum"], [str(b.pk) for b in self.books])
        self.assertEqual(item["required"], ["book_id", "reason", "quote"])
        listing = body["contents"][0]["parts"][0]["text"]
        for book in self.books:
            self.assertIn(f"id {book.pk}: {book.title}", listing)
        self.assertIn("Jonathan Harker travels", listing)
        self.assertLess(listing.count("More of the story."), 60)  # long summaries are cut
        self.assertTrue(listing.endswith("Question: algo de miedo"))  # the catalog first, the question last

    def test_the_catalog_keeps_its_order_when_books_are_added(self):
        make_book(title="A book that sorts first by title")
        self.assertEqual(librarian.catalog()[-1].title, "A book that sorts first by title")


class QuoteTests(SimpleTestCase):
    def test_a_word_for_word_excerpt_passes_give_or_take_case_spacing_and_marks(self):
        summary = "He finds himself a prisoner in the castle — and the Count’s guest."
        self.assertTrue(librarian.quote_in_summary("finds himself a prisoner in the castle", summary))
        self.assertTrue(librarian.quote_in_summary("“Finds  himself a PRISONER in the castle…”", summary))
        self.assertTrue(librarian.quote_in_summary("in the castle - and the Count's guest", summary))

    def test_quotation_marks_do_not_count(self):
        summary = '"Vida De Lazarillo De Tormes" by Anonymous is a Spanish novel published in 1554.'
        self.assertTrue(librarian.quote_in_summary("Vida De Lazarillo De Tormes by Anonymous is a Spanish novel", summary))

    def test_a_paraphrase_or_a_scrap_does_not(self):
        summary = "He finds himself a prisoner in the castle."
        self.assertFalse(librarian.quote_in_summary("he is held captive in the castle", summary))
        self.assertFalse(librarian.quote_in_summary("the castle", summary))
        self.assertFalse(librarian.quote_in_summary("“Azul...”", '"Azul..." by Rubén Darío is a collection of prose and poetry.'))


class CheckTests(LibrarianTestCase):
    def test_a_quote_must_come_from_that_books_own_summary(self):
        picks, dropped = librarian.check_picks(text(
            (self.dracula.pk, "Miedo clásico.", "finds himself a prisoner in the castle"),
            (self.quijote.pk, "Not backed.", "finds himself a prisoner in the castle"),   # Dracula's line, not his
            (self.platero.pk, "Invented line.", "a donkey who fights vampires at night")), self.books)
        self.assertEqual([b for b, _, _ in picks], [self.dracula])
        self.assertEqual(dropped, 2)

    def test_a_pick_without_a_quote_is_the_models_knowledge(self):
        picks, dropped = librarian.check_picks(text(
            (self.quijote.pk, "Los molinos de viento.", ""), (self.platero.pk, "Un burro y un poeta.")), self.books)
        self.assertEqual(picks, [(self.quijote, "Los molinos de viento.", None), (self.platero, "Un burro y un poeta.", None)])
        self.assertEqual(dropped, 0)

    def test_invented_ids_empty_reasons_repeats_and_extras_are_dropped(self):
        extra = make_book(title="Extra")
        picks, dropped = librarian.check_picks(text(
            (99999, "Not listed."), (self.quijote.pk, "  "), (self.dracula.pk, "Yes."), (self.dracula.pk, "Again."),
            (self.platero.pk, "Two."), (extra.pk, "Three."), (self.quijote.pk, "Four.")), self.books + [extra])
        self.assertEqual([b for b, _, _ in picks], [self.dracula, self.platero, extra])
        self.assertEqual(dropped, 4)

    def test_an_answer_that_is_not_the_json_asked_for_passes_nothing(self):
        for answer in ("Dracula, obviously.", "[]", '{"picks": "Dracula"}'):
            with self.subTest(answer=answer):
                self.assertEqual(librarian.check_picks(answer, self.books), ([], 1))

    def test_cards_keep_the_models_order(self):
        cards = librarian.cards([(self.platero, "R1", None), (self.dracula, "R2", "q2")])
        self.assertEqual([(c["book"], c["reason"], c["quote"]) for c in cards],
                         [(self.platero, "R1", None), (self.dracula, "R2", "q2")])


@override_settings(GEMINI_API_KEY="site-key")
class SiteKeyTests(LibrarianTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(make_user())
        self.url = reverse("librarian")

    def ask(self, *answers):
        with mock.patch("library.views.call", side_effect=list(answers)) as fake:
            return self.client.post(self.url, {"question": "algo de miedo"}), fake

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_one_call_with_the_whole_catalog_both_kinds_labelled_and_logged(self):
        response, fake = self.ask(gemini_says(
            (self.dracula.pk, "Un conde vampiro.", "finds himself a prisoner in the castle"),
            (self.quijote.pk, "Bad quote.", "windmills everywhere in this summary"),
            (self.platero.pk, "Juan Ramón Jiménez's prose poem.", ""),
            (424242, "Invented.", "")))
        self.assertEqual(fake.call_count, 1)
        self.assertIn("Platero y yo", fake.call_args.args[2]["contents"][0]["parts"][0]["text"])
        self.assertContains(response, "From its summary")
        self.assertContains(response, "“finds himself a prisoner in the castle”")
        self.assertContains(response, "What the librarian knows")
        self.assertContains(response, "Juan Ramón Jiménez&#x27;s prose poem.")
        self.assertNotContains(response, "Bad quote.")
        self.assertNotContains(response, "Invented.")
        self.assertContains(response, "The check removed 2 suggestions")
        log = LibrarianAnswer.objects.get()
        self.assertEqual((log.picks, log.knowledge_picks, log.dropped, log.key),
                         ([self.dracula.pk], [self.platero.pk], 2, "site"))

    def test_nothing_fits(self):
        response, _ = self.ask(gemini_says())
        self.assertContains(response, "Nothing in the catalog fits")

    @override_settings(LIBRARIAN_QUESTIONS_PER_READER_PER_DAY=1)
    def test_daily_cap_stops_before_calling_gemini(self):
        self.ask(gemini_says())
        response, fake = self.ask(gemini_says())
        fake.assert_not_called()
        self.assertContains(response, "used up")

    def test_provider_error_is_explained(self):
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

    def librarian_request(self, question="algo de miedo"):
        return self.post_json("librarian_request", {"question": question})

    def test_without_a_site_key_the_form_does_not_post(self):
        self.assertEqual(self.client.post(reverse("librarian"), {"question": "algo"}).status_code, 400)
        self.assertContains(self.client.get(reverse("librarian")), 'data-site-key="false"')

    def test_the_request_brings_the_whole_catalog(self):
        data = self.librarian_request().json()
        enum = data["body"]["generationConfig"]["responseSchema"]["properties"]["picks"]["items"]["properties"]["book_id"]["enum"]
        self.assertEqual(enum, [str(b.pk) for b in self.books])
        self.assertEqual(data["model"], "gemini-3.5-flash-lite")

    def test_an_empty_question_is_refused(self):
        self.assertEqual(self.librarian_request("   ").status_code, 400)

    def test_the_answer_is_checked_against_the_catalog_once(self):
        token = self.librarian_request().json()["token"]
        payload = {"token": token, "text": text((self.dracula.pk, "Castillo.", "finds himself a prisoner in the castle"),
                                               (self.quijote.pk, "Molinos.", ""), (31337, "Invented.", ""))}
        html = self.post_json("librarian_answer", payload).json()["html"]
        self.assertIn("Castillo.", html)
        self.assertIn("Molinos.", html)
        self.assertNotIn("Invented.", html)
        log = LibrarianAnswer.objects.get()
        self.assertEqual((log.picks, log.knowledge_picks, log.dropped, log.key),
                         ([self.dracula.pk], [self.quijote.pk], 1, "reader"))
        self.assertEqual(self.post_json("librarian_answer", payload).status_code, 400)

    def test_another_readers_token_is_refused(self):
        token = self.librarian_request().json()["token"]
        self.client.force_login(make_user("someone-else"))
        self.assertEqual(self.post_json("librarian_answer", {"token": token, "text": "{}"}).status_code, 400)

    def test_ai_key_page_never_posts_the_key(self):
        response = self.client.get(reverse("ai_key"))
        self.assertContains(response, 'id="ai-key-form"')
        self.assertNotContains(response, 'method="post"')
