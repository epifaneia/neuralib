from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from library.gutenberg import book_fields, popular_books
from library.models import Book


def item(gid=61851, **changes):
    """One Gutendex result, shaped like the real API's."""
    data = {
        "id": gid,
        "title": "El crimen y el castigo",
        "authors": [{"name": "Dostoyevsky, Fyodor", "birth_year": 1821, "death_year": 1881}],
        "summaries": ['"El crimen y el castigo" by Fyodor Dostoyevsky is a novel. A former student plans a murder. '
                      "(This is an automatically generated summary.)"],
        "subjects": ["Crime -- Psychological aspects -- Fiction", "Murder -- Fiction"],
        "bookshelves": ["Category: Classics of Literature", "Category: Novels", "Best Books Ever Listings"],
        "languages": ["es"],
        "copyright": False,
        "media_type": "Text",
        "formats": {"text/html": "https://www.gutenberg.org/ebooks/61851.html.images",
                    "application/epub+zip": "https://www.gutenberg.org/ebooks/61851.epub3.images",
                    "image/jpeg": "https://www.gutenberg.org/cache/epub/61851/pg61851.cover.medium.jpg"},
        "download_count": 29958,
    }
    data.update(changes)
    return data


class BookFieldsTests(SimpleTestCase):
    def test_maps_a_gutendex_result(self):
        fields = book_fields(item())
        self.assertEqual(fields["writer"], "Fyodor Dostoyevsky")
        self.assertEqual(fields["genre"], "Classics of Literature · Novels")
        self.assertEqual(fields["subjects"], "Crime -- Psychological aspects -- Fiction; Murder -- Fiction")
        self.assertEqual(fields["language"], "es")
        self.assertTrue(fields["download_link"].endswith(".epub3.images"))

    def test_generated_summary_is_flagged_and_the_note_removed(self):
        fields = book_fields(item())
        self.assertTrue(fields["summary_is_generated"])
        self.assertNotIn("automatically generated", fields["description"])

    def test_skips_what_cannot_be_a_catalog_entry(self):
        for changes in ({"copyright": True}, {"media_type": "Sound"}, {"summaries": []}):
            with self.subTest(**changes):
                self.assertIsNone(book_fields(item(**changes)))

    def test_catalog_subfield_codes_are_removed_from_titles(self):
        self.assertEqual(book_fields(item(title="Boston : $b a novel"))["title"], "Boston: a novel")
        self.assertEqual(book_fields(item(title="A $100 bet"))["title"], "A $100 bet")

    def test_no_authors_means_anonymous(self):
        self.assertEqual(book_fields(item(authors=[]))["writer"], "Anonymous")

    def test_popular_books_follows_pages_and_stops_at_count(self):
        pages = {
            "https://gutendex.com/books/?languages=es": {"results": [item(1), item(2, copyright=True)], "next": "page2"},
            "page2": {"results": [item(3), item(4)], "next": None},
        }
        with mock.patch("library.gutenberg.fetch_json", side_effect=pages.__getitem__):
            self.assertEqual([gid for gid, _ in popular_books("es", 2)], [1, 3])


class ImportCommandTests(TestCase):
    def run_import(self, results):
        page = {"results": results, "next": None}
        with mock.patch("library.gutenberg.fetch_json", return_value=page):
            out = StringIO()
            call_command("import_gutenberg", "--language", "es", "--count", "10", stdout=out)
        return out.getvalue()

    def test_imports_and_running_again_updates_instead_of_duplicating(self):
        self.assertIn("es: 2 created, 0 updated.", self.run_import([item(1), item(2)]))
        self.assertIn("es: 0 created, 2 updated.", self.run_import([item(1), item(2, title="Renamed")]))
        self.assertEqual(Book.objects.count(), 2)
        self.assertTrue(Book.objects.filter(gutenberg_id=2, title="Renamed").exists())
