from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from library.admin import import_books
from library.models import Book

HEADER = "title,description,genre,num_pages,editorial,year_edition,writer,image_url,read_online,download_link,isbn\n"
DUNE = "Dune,Spice and sand,science_fiction_new,412,Chilton,1965,Frank Herbert,,,,9780441013593\n"
HOBBIT_NO_ISBN = "The Hobbit,There and back,fantasy_magic,310,Allen & Unwin,1937,Tolkien,,,\n"


class ImportBooksTests(TestCase):
    def test_imports_rows_with_and_without_isbn(self):
        created, errors = import_books(HEADER + DUNE + HOBBIT_NO_ISBN)
        self.assertEqual((created, errors), (2, []))
        self.assertEqual(Book.objects.get(title="Dune").isbn, "9780441013593")
        self.assertIsNone(Book.objects.get(title="The Hobbit").image_url)

    def test_wrong_column_count_is_reported(self):
        created, errors = import_books(HEADER + "Too,short\n")
        self.assertEqual(created, 0)
        self.assertIn("Line 2", errors[0])

    def test_invalid_values_are_reported_and_skipped(self):
        bad = "Bad,X,cooking,lots,X,1999,X,,,,\n"
        created, errors = import_books(HEADER + bad + DUNE)
        self.assertEqual(created, 1)
        self.assertEqual(len(errors), 1)


class ImportCSVViewTests(TestCase):
    def setUp(self):
        admin = get_user_model().objects.create_superuser("admin", "admin@example.com", "a-long-test-password")
        self.client.force_login(admin)
        self.url = reverse("admin:library_book_import_csv")

    def upload(self, content, name="books.csv"):
        return self.client.post(self.url, {"csv_file": SimpleUploadedFile(name, content)}, follow=True)

    def test_form_loads(self):
        self.assertContains(self.client.get(self.url), "Import books from CSV")

    def test_upload_creates_books(self):
        response = self.upload((HEADER + DUNE).encode())
        self.assertContains(response, "1 book(s) imported.")
        self.assertTrue(Book.objects.filter(title="Dune").exists())

    def test_non_utf8_file_is_rejected(self):
        response = self.upload((HEADER + "Caf\xe9,X,fantasy_magic,1,X,2000,X,,,,\n").encode("latin-1"))
        self.assertContains(response, "not in UTF-8")
        self.assertFalse(Book.objects.exists())

    def test_staff_only(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin:login"), response.url)
