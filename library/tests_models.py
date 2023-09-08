from django.test import TestCase
from library.forms import SearchForm, CSVImportForm
from django.core.files.uploadedfile import SimpleUploadedFile
from library.models import Book


class BookModelTest(TestCase):
    def test_book_creation(self):
        Book.objects.create(
            title="Sample Book",
            description="Sample Description",
            genre="folk_tales",
            num_pages=100,
            editorial="Sample Editorial",
            isbn="1234567890123",
            year_edition=2023,
            date_edition="2023-01-01",
            writer="John Doe",
        )
        book = Book.objects.get(id=1)
        self.assertEqual(book.title, "Sample Book")
        self.assertEqual(book.description, "Sample Description")
        self.assertEqual(str(book), "Sample Book")

    def test_book_str_method(self):
        book = Book(
            title="Another Book",
            description="Another Description",
            genre="fantasy_magic",
            num_pages=150,
            editorial="Another Editorial",
            isbn="9876543210987",
            year_edition=2022,
            date_edition="2022-12-01",
            writer="Jane Doe",
        )
        self.assertEqual(str(book), "Another Book")


class SearchFormTest(TestCase):
    def test_empty_fields(self):
        form = SearchForm(data={})
        self.assertFalse(form.is_valid())

    def test_valid_options(self):
        valid_data = {'query': 'Test', 'field': 'title'}
        form = SearchForm(data=valid_data)
        self.assertTrue(form.is_valid())

    def test_invalid_field_option(self):
        invalid_data = {'query': 'Test', 'field': 'invalid_option'}
        form = SearchForm(data=invalid_data)
        self.assertFalse(form.is_valid())


class CSVImportFormTest(TestCase):
    def test_valid_csv_file(self):
        csv_file = SimpleUploadedFile("file.csv", b"file_content")
        form = CSVImportForm(files={'csv_file': csv_file})
        self.assertTrue(form.is_valid())

    def test_invalid_file(self):
        txt_file = SimpleUploadedFile("file.txt", b"file_content")
        form = CSVImportForm(files={'csv_file': txt_file})
        self.assertFalse(form.is_valid())
