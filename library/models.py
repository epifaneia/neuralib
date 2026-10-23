from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Book(models.Model):
    GENRE_CHOICES = (
        ("folk_tales", "Folk tales"),
        ("fantasy_magic", "Fantasy and magic"),
        ("african_history", "History of African countries"),
        ("children_10_12", "Children's literature for 10 to 12 year olds"),
        ("french_literature", "French literature"),
        ("spanish_literature", "Spanish literature"),
        ("science_fiction_new", "Science fiction"),
        ("humorous_fiction", "Humorous fiction"),
        ("horror_fiction", "Horror fiction"),
        ("travel_literature", "Travel literature"),
        ("foreign_lit_18th", "Foreign literature up to the 18th century"),
        ("fantastic_fiction", "Fantastic fiction"),
        ("horror_pocketbooks", "Horror pocketbooks"),
    )

    title = models.CharField(max_length=200)
    description = models.TextField()
    genre = models.CharField(max_length=50, choices=GENRE_CHOICES)
    num_pages = models.PositiveIntegerField()
    editorial = models.CharField(max_length=100)
    year_edition = models.PositiveIntegerField()
    writer = models.CharField(max_length=100)
    isbn = models.CharField("ISBN", max_length=17, blank=True, db_index=True)
    image_url = models.URLField(blank=True, null=True)
    read_online = models.URLField(blank=True, null=True)
    download_link = models.URLField(blank=True, null=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


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
