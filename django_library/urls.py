from django.contrib import admin
from django.urls import include, path

from library import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", views.library_home, name="library_home"),
    path("catalog/", views.catalog, name="catalog"),
    path("reviews/", views.reviews, name="reviews"),
    path("users/", views.users, name="users"),
    path("add_review/", views.add_review, name="add_review"),
    path("books/<int:book_id>/review/", views.review_book, name="review_book"),
    path("librarian/", views.ask_librarian, name="librarian"),
    path("librarian/candidates/", views.librarian_candidates, name="librarian_candidates"),
    path("librarian/answer/", views.librarian_answer, name="librarian_answer"),
    path("accounts/ai-key/", views.ai_key, name="ai_key"),
]
