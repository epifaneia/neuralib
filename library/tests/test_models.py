from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from library.models import Book

from .factories import make_book, make_review, make_user


class BookTests(TestCase):
    def test_str_is_title(self):
        self.assertEqual(str(make_book()), "The Hobbit")

    def test_books_are_ordered_by_title(self):
        make_book(title="Zorba")
        make_book(title="Animal Farm")
        self.assertEqual([b.title for b in Book.objects.all()], ["Animal Farm", "Zorba"])

    def test_edition_fields_are_optional(self):
        # Project Gutenberg gives no pages, editorial or edition year.
        Book(title="X", description="X", writer="X").full_clean()

    def test_gutenberg_id_is_unique(self):
        make_book(gutenberg_id=2000)
        with self.assertRaises(IntegrityError):
            make_book(title="Other", gutenberg_id=2000)


class ReviewTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.book = make_book()

    def test_str_names_book_and_reader(self):
        review = make_review(self.user, self.book)
        self.assertEqual(str(review), "Review of The Hobbit by reader")

    def test_one_review_per_reader_and_book(self):
        make_review(self.user, self.book)
        with self.assertRaises(IntegrityError):
            make_review(self.user, self.book, title="Again")

    def test_rating_must_be_between_1_and_5(self):
        for rating in (0, 6):
            review = make_review(make_user(f"r{rating}"), self.book, rating=rating)
            with self.assertRaises(ValidationError):
                review.full_clean()

    def test_newest_reviews_first(self):
        first = make_review(self.user, self.book)
        second = make_review(make_user("other"), self.book)
        self.assertEqual(list(self.book.reviews.all()), [second, first])
