import io
import json
import urllib.error
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from library.embeddings import DIMENSIONS, book_text, embed
from library.gemini import GeminiError, QuotaExceeded
from library.models import Book

from .factories import make_book


def axis(i):
    """A vector pointing along one axis: its cosine distance to any other axis is 1."""
    v = [0.0] * DIMENSIONS
    v[i] = 1.0
    return v


def answer(n):
    """A fake HTTP response from batchEmbedContents with n vectors."""
    return io.BytesIO(json.dumps({"embeddings": [{"values": axis(0)} for _ in range(n)]}).encode())


@override_settings(GEMINI_API_KEY="test-key")
class EmbedTests(SimpleTestCase):
    def test_key_goes_in_a_header_and_texts_in_batches(self):
        sent = []

        def urlopen(request, timeout):
            sent.append(request)
            return answer(len(json.loads(request.data)["requests"]))

        with mock.patch("urllib.request.urlopen", side_effect=urlopen):
            vectors = embed([f"book {i}" for i in range(120)], "RETRIEVAL_DOCUMENT")
        self.assertEqual(len(vectors), 120)
        self.assertEqual(len(sent), 3)
        self.assertEqual(sent[0].get_header("X-goog-api-key"), "test-key")
        self.assertNotIn("test-key", sent[0].full_url)
        first = json.loads(sent[0].data)["requests"][0]
        self.assertEqual((first["taskType"], first["outputDimensionality"]), ("RETRIEVAL_DOCUMENT", DIMENSIONS))

    def test_rate_limit_is_reported_not_retried(self):
        error = urllib.error.HTTPError("url", 429, "Too Many Requests", {}, io.BytesIO(b""))
        with mock.patch("urllib.request.urlopen", side_effect=error) as urlopen:
            with self.assertRaises(QuotaExceeded):
                embed(["a"], "RETRIEVAL_QUERY")
        self.assertEqual(urlopen.call_count, 1)

    def test_unexpected_answer_is_an_error(self):
        short = io.BytesIO(json.dumps({"embeddings": [{"values": [0.1, 0.2]}]}).encode())
        with mock.patch("urllib.request.urlopen", return_value=short):
            with self.assertRaises(GeminiError):
                embed(["a"], "RETRIEVAL_QUERY")

    @override_settings(GEMINI_API_KEY="")
    def test_no_key_is_an_error_before_any_call(self):
        with mock.patch("urllib.request.urlopen") as urlopen:
            with self.assertRaises(GeminiError):
                embed(["a"], "RETRIEVAL_QUERY")
        urlopen.assert_not_called()


class BookTextTests(SimpleTestCase):
    def test_joins_what_the_book_is_and_skips_empty_parts(self):
        book = Book(title="Dune", writer="Frank Herbert", genre="", subjects="Desert", description="Spice.")
        self.assertEqual(book_text(book), "Dune\nFrank Herbert\nDesert\nSpice.")


class EmbedBooksCommandTests(TestCase):
    def run_command(self):
        out = io.StringIO()
        with mock.patch("library.management.commands.embed_books.embed",
                        side_effect=lambda texts, task: [axis(0) for _ in texts]) as fake:
            call_command("embed_books", stdout=out)
        return out.getvalue(), fake

    def test_embeds_new_books_then_only_changed_ones(self):
        hobbit, _ = make_book(), make_book(title="Dune")
        self.assertIn("2 book(s) embedded.", self.run_command()[0])
        output, fake = self.run_command()
        self.assertIn("0 book(s) to embed.", output)
        fake.assert_not_called()
        hobbit.description = "Rewritten."
        hobbit.save()
        self.assertIn("1 book(s) embedded.", self.run_command()[0])


class SemanticSearchViewTests(TestCase):
    def setUp(self):
        cache.clear()
        for i, title in enumerate(["Dracula", "Platero y yo", "Don Quijote"]):
            book = make_book(title=title)
            book.embedding = axis(i)
            book.save()
        make_book(title="Not embedded yet")

    def search(self, query):
        return self.client.get(reverse("catalog"), {"query": query, "field": "meaning"})

    def test_closest_in_meaning_first(self):
        with mock.patch("library.search.query_vector", return_value=axis(2)):
            response = self.search("caballero que lucha contra molinos")
        titles = [b.title for b in response.context["books"]]
        self.assertEqual(titles[0], "Don Quijote")
        self.assertNotIn("Not embedded yet", titles)
        self.assertTrue(response.context["semantic"])

    @override_settings(SEMANTIC_SEARCHES_PER_VISITOR_PER_DAY=1)
    def test_daily_cap_falls_back_to_title_search_without_calling_the_api(self):
        with mock.patch("library.search.query_vector", return_value=axis(0)) as fake:
            self.search("vampiros")
            response = self.search("Dracula")
        self.assertEqual(fake.call_count, 1)
        self.assertContains(response, "used up")
        self.assertEqual([b.title for b in response.context["books"]], ["Dracula"])

    @override_settings(SEMANTIC_SEARCHES_PER_VISITOR_PER_DAY=1)
    def test_repeating_a_search_does_not_spend_the_cap(self):
        # The real query_vector, so its cache is the one that saves the second call.
        with mock.patch("library.embeddings.embed", return_value=[axis(0)]) as fake:
            self.search("vampiros")
            response = self.search("Vampiros ")
        self.assertEqual(fake.call_count, 1)
        self.assertTrue(response.context["semantic"])

    def test_provider_error_falls_back_to_title_search(self):
        with mock.patch("library.search.query_vector", side_effect=QuotaExceeded("busy")):
            response = self.search("Platero")
        self.assertContains(response, "not available right now")
        self.assertEqual([b.title for b in response.context["books"]], ["Platero y yo"])
