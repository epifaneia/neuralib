from django.db import models
from django.contrib.auth.models import User

# Create your models here.


class Book(models.Model):
    GENRE_CHOICES = (
        ('folk_tales', 'Folk tales'),
        ('fantasy_magic', 'Fantasy and magic'),
        ('african_history', 'History of African countries'),
        ('children_10_12', 'Children\'s literature for 10 to 12 year olds'),
        ('french_literature',  'French literature'),
        ('spanish_literature', 'Spanish literature'),
        ('science_fiction_new', 'Science fiction'),
        ('humorous_fiction', 'Humorous fiction'),
        ('horror_fiction', 'Horror fiction'),
        ('travel_literature', 'Travel literature'),
        ('foreign_lit_18th', 'Foreign literature up to the 18th century'),
        ('fantastic_fiction', 'Fantastic fiction'),
        ('horror_pocketbooks', 'Horror pocketbooks'),
    )

    title = models.CharField(max_length=200)
    description = models.TextField()
    genre = models.CharField(max_length=50, choices=GENRE_CHOICES)
    num_pages = models.PositiveIntegerField()
    editorial = models.CharField(max_length=100)
    year_edition = models.PositiveIntegerField()
    writer = models.CharField(max_length=100)
    image_url = models.URLField(blank=True, null=True)
    read_online = models.URLField(null=True, blank=True)
    download_link = models.URLField(null=True, blank=True)

    def __str__(self):
        return self.title

class UserCustom(models.Model):
    username = models.CharField(max_length=50, unique=True)
    
    def __str__(self):
        return self.username

class Review(models.Model):
    title = models.CharField(max_length=255, default="Untitled")
    user = models.ForeignKey(UserCustom, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True, null=True)

    
    def __str__(self):
        return f"Review of {self.book.title} by {self.user.username}"

class Rating(models.Model):
    user = models.ForeignKey(UserCustom, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    score = models.IntegerField(choices=[(i, str(i)) for i in range(1, 6)])  # 1 to 5
    
    def __str__(self):
        return f"Rating of {self.book.title} by {self.user.username} is {self.score}"

class PrivateComment(models.Model):
    from_user = models.ForeignKey(UserCustom, related_name='comments_sent', on_delete=models.CASCADE)
    to_user = models.ForeignKey(UserCustom, related_name='comments_received', on_delete=models.CASCADE)
    content = models.TextField()
    
    def __str__(self):
        return f"Comment from {self.from_user.username} to {self.to_user.username}"