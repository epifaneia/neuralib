from django.contrib.auth import get_user_model

from library.models import Book, Review


def make_book(**fields):
    data = {
        "title": "The Hobbit",
        "description": "A hobbit goes there and back again.",
        "genre": "fantasy_magic",
        "num_pages": 310,
        "editorial": "Allen & Unwin",
        "year_edition": 1937,
        "writer": "J. R. R. Tolkien",
    }
    data.update(fields)
    return Book.objects.create(**data)


def make_user(username="reader", password="a-long-test-password"):
    return get_user_model().objects.create_user(username=username, password=password)


def make_review(user, book, **fields):
    data = {"title": "Lovely", "rating": 5, "content": "Read it twice."}
    data.update(fields)
    return Review.objects.create(user=user, book=book, **data)
