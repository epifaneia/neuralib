from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from pgvector.django import HnswIndex, VectorField

from .embeddings import DIMENSIONS


class Book(models.Model):
    """A catalog entry. Books imported from Project Gutenberg carry its id; the
    edition fields (pages, editorial, year) stay empty for them."""

    title = models.CharField(max_length=200)
    description = models.TextField()
    summary_is_generated = models.BooleanField(
        default=False, help_text="The description is an automatically generated summary (Project Gutenberg's).")
    genre = models.CharField("category", max_length=200, blank=True)
    subjects = models.TextField(blank=True)
    language = models.CharField(max_length=8, blank=True, db_index=True)
    num_pages = models.PositiveIntegerField(null=True, blank=True)
    editorial = models.CharField(max_length=100, blank=True)
    year_edition = models.PositiveIntegerField(null=True, blank=True)
    writer = models.CharField(max_length=200)
    isbn = models.CharField("ISBN", max_length=17, blank=True, db_index=True)
    gutenberg_id = models.PositiveIntegerField(null=True, blank=True, unique=True)
    image_url = models.URLField(blank=True, null=True)
    read_online = models.URLField(blank=True, null=True)
    download_link = models.URLField(blank=True, null=True)
    # Semantic search. The hash says what text the vector was made from, so only changed books are embedded again.
    embedding = VectorField(dimensions=DIMENSIONS, null=True, blank=True, editable=False)
    embedding_hash = models.CharField(max_length=64, blank=True, editable=False)

    class Meta:
        ordering = ["title"]
        indexes = [
            HnswIndex(name="book_embedding_hnsw", fields=["embedding"], m=16, ef_construction=64,
                      opclasses=["vector_cosine_ops"]),
        ]

    def __str__(self):
        return self.title


class LibrarianAnswer(models.Model):
    """One question to the librarian and what passed the check. No reader is stored."""

    question = models.TextField()
    picks = models.JSONField(default=list, help_text="Ids of the books recommended, in order.")
    dropped = models.PositiveSmallIntegerField(default=0, help_text="Picks the check removed: not in the list, no reason, repeated or over the limit.")
    model = models.CharField(max_length=60)
    key = models.CharField(max_length=10, choices=[("site", "Site key"), ("reader", "Reader's own key")])
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return self.question[:60]


class Review(models.Model):
    """One review per reader and book, with a 1–5 rating."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="reviews")
    title = models.CharField(max_length=255)
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        constraints = [
            models.UniqueConstraint(fields=["user", "book"], name="one_review_per_user_and_book"),
        ]

    def __str__(self):
        return f"Review of {self.book.title} by {self.user.username}"
