from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from library.forms import CSVImportForm, ReviewForm, SearchForm


class SearchFormTests(SimpleTestCase):
    def test_valid_search(self):
        self.assertTrue(SearchForm({"query": "tolkien", "field": "writer"}).is_valid())

    def test_unknown_field_is_rejected(self):
        # The field name ends up in an ORM lookup, so only listed choices may pass.
        self.assertFalse(SearchForm({"query": "x", "field": "password"}).is_valid())

    def test_empty_query_is_rejected(self):
        self.assertFalse(SearchForm({"query": "", "field": "title"}).is_valid())


class ReviewFormTests(SimpleTestCase):
    def test_valid_review(self):
        form = ReviewForm({"title": "Good", "rating": "4", "content": "Nice."})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["rating"], 4)

    def test_rating_out_of_range(self):
        self.assertFalse(ReviewForm({"title": "Bad", "rating": "9", "content": "x"}).is_valid())


class CSVImportFormTests(SimpleTestCase):
    def test_accepts_csv(self):
        upload = SimpleUploadedFile("books.csv", b"title\n", content_type="text/csv")
        self.assertTrue(CSVImportForm(files={"csv_file": upload}).is_valid())

    def test_rejects_other_extensions(self):
        upload = SimpleUploadedFile("books.xlsx", b"x")
        self.assertFalse(CSVImportForm(files={"csv_file": upload}).is_valid())
