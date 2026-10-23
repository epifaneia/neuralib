from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ReviewForm, ReviewSearchForm, SearchForm, UserSearchForm
from .models import Book, Review

PAGE_SIZE = 5

# Search field -> ORM lookup. Only these keys can reach the database.
BOOK_LOOKUPS = {
    "title": "title__icontains",
    "writer": "writer__icontains",
    "genre": "genre__icontains",
    "editorial": "editorial__icontains",
    "isbn": "isbn__icontains",
}
REVIEW_LOOKUPS = {
    "title": "title__icontains",
    "book": "book__title__icontains",
    "user": "user__username__icontains",
}


def _paginate(request, queryset):
    return Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("page"))


def _search(request, form_class, queryset, lookups):
    """Filter `queryset` with the GET search form. An invalid or empty form returns everything."""
    form = form_class(request.GET or None)
    query = ""
    if form.is_valid():
        query = form.cleaned_data["query"]
        queryset = queryset.filter(**{lookups[form.cleaned_data["field"]]: query})
    return form, queryset, query


def _book_context(request):
    form, books, query = _search(request, SearchForm, Book.objects.all(), BOOK_LOOKUPS)
    return {"form": form, "books": _paginate(request, books), "query": query}


def library_home(request):
    context = _book_context(request)
    context["latest_reviews"] = Review.objects.select_related("book", "user")[:3]
    return render(request, "library/library_home.html", context)


def catalog(request):
    return render(request, "library/catalog.html", _book_context(request))


def reviews(request):
    queryset = Review.objects.select_related("book", "user")
    form, queryset, query = _search(request, ReviewSearchForm, queryset, REVIEW_LOOKUPS)
    return render(request, "library/reviews.html", {"form": form, "reviews": _paginate(request, queryset), "query": query})


def users(request):
    form = UserSearchForm(request.GET or None)
    queryset = get_user_model().objects.filter(is_active=True).annotate(num_reviews=Count("reviews")).order_by("username")
    query = ""
    if form.is_valid():
        query = form.cleaned_data["query"]
        queryset = queryset.filter(username__icontains=query)
    return render(request, "library/users.html", {"form": form, "users": _paginate(request, queryset), "query": query})


@login_required
def add_review(request):
    """Pick a book to review: the catalog search, with a 'review' link on each book."""
    return render(request, "library/add_review.html", _book_context(request))


@login_required
def review_book(request, book_id):
    """Write a review, or edit yours if you already reviewed this book."""
    book = get_object_or_404(Book, pk=book_id)
    existing = Review.objects.filter(user=request.user, book=book).first()
    form = ReviewForm(request.POST or None, instance=existing)
    if request.method == "POST" and form.is_valid():
        review = form.save(commit=False)
        review.user = request.user
        review.book = book
        review.save()
        messages.success(request, "Review updated." if existing else "Review published.")
        return redirect("reviews")
    return render(request, "library/review_book.html", {"form": form, "book": book, "editing": existing is not None})
