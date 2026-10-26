import json
import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from . import librarian
from .embeddings import DIMENSIONS, cached_query_vector, query_vector
from .forms import ReviewForm, ReviewSearchForm, SearchForm, UserSearchForm
from .gemini import GeminiError, call, generated_text
from .models import Book, LibrarianAnswer, Review
from .search import SearchLimitReached, semantic_search, spend_one

PAGE_SIZE = 5

# Search field -> ORM lookup. Only these keys can reach the database.
BOOK_LOOKUPS = {
    "title": "title__icontains",
    "writer": "writer__icontains",
    "subjects": "subjects__icontains",
    "genre": "genre__icontains",
    "language": "language__iexact",
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
    form = SearchForm(request.GET or None)
    books, query, semantic = Book.objects.all(), "", False
    if form.is_valid():
        query, field = form.cleaned_data["query"], form.cleaned_data["field"]
        if field == "meaning":
            try:
                books, semantic = semantic_search(request, query), True
            except SearchLimitReached:
                messages.info(request, "Today's AI searches are used up, so these results match the title only.")
                books = books.filter(title__icontains=query)
            except GeminiError:
                messages.warning(request, "AI search is not available right now, so these results match the title only.")
                books = books.filter(title__icontains=query)
        else:
            books = books.filter(**{BOOK_LOOKUPS[field]: query})
    return {"form": form, "books": _paginate(request, books), "query": query, "semantic": semantic}


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


# The librarian. With the site's key the page posts its form here and the server calls Gemini.
# With a reader's own key the page's script calls Gemini from the browser, so the key never
# reaches this server, and uses the two JSON views below for the closed list and the check.

def _log(question, picks, dropped, key):
    LibrarianAnswer.objects.create(question=question, picks=[b.pk for b, _ in picks], dropped=dropped,
                                   model=settings.LIBRARIAN_MODEL, key=key)


@login_required
def ask_librarian(request):
    context = {"site_key": bool(settings.GEMINI_API_KEY), "question": "", "picks": None, "dropped": 0,
               "embedding_model": settings.EMBEDDING_MODEL, "dimensions": DIMENSIONS,
               "question_max": librarian.QUESTION_MAX}
    if request.method == "POST":
        if not settings.GEMINI_API_KEY:
            return HttpResponseBadRequest("This site has no key of its own: add yours on the AI key page.")
        question = request.POST.get("question", "").strip()[:librarian.QUESTION_MAX]
        context["question"] = question
        if question and not spend_one(request, "librarian", settings.LIBRARIAN_QUESTIONS_PER_READER_PER_DAY,
                                      settings.LIBRARIAN_QUESTIONS_PER_DAY):
            messages.info(request, "Today's questions to the librarian are used up. You can use your own key from the AI key page.")
        elif question:
            try:
                books = librarian.candidates(cached_query_vector(question) or query_vector(question))
                answer = call(settings.LIBRARIAN_MODEL, "generateContent", librarian.request_body(question, books))
                picks, dropped = librarian.check_picks(generated_text(answer), books)
            except GeminiError:
                messages.warning(request, "The librarian cannot answer right now. Try again in a while.")
            else:
                _log(question, picks, dropped, "site")
                context.update(picks=picks, dropped=dropped)
    return render(request, "library/librarian.html", context)


def _json_body(request):
    try:
        data = json.loads(request.body)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


@login_required
@require_POST
def librarian_candidates(request):
    """Reader's own key, step 1: the question's vector in, the closed list and the request to send to Gemini out."""
    data = _json_body(request)
    question = str(data.get("question", "")).strip()[:librarian.QUESTION_MAX]
    vector = data.get("vector")
    if not question or not isinstance(vector, list) or len(vector) != DIMENSIONS             or not all(isinstance(x, (int, float)) for x in vector):
        return JsonResponse({"error": "A question and its vector are needed."}, status=400)
    books = librarian.candidates(vector)
    token = secrets.token_urlsafe(16)
    cache.set(f"librarian:{token}", {"question": question, "ids": [b.pk for b in books], "user": request.user.pk}, 600)
    return JsonResponse({"token": token, "model": settings.LIBRARIAN_MODEL,
                         "body": librarian.request_body(question, books)})


@login_required
@require_POST
def librarian_answer(request):
    """Reader's own key, step 2: the model's raw answer in, checked against that same list, the page fragment out."""
    data = _json_body(request)
    key = f"librarian:{data.get('token', '')}"
    pending = cache.get(key)
    if not pending or pending["user"] != request.user.pk:
        return JsonResponse({"error": "This question expired. Ask it again."}, status=400)
    cache.delete(key)
    found = Book.objects.in_bulk(pending["ids"])
    books = [found[pk] for pk in pending["ids"] if pk in found]
    picks, dropped = librarian.check_picks(str(data.get("text", "")), books)
    _log(pending["question"], picks, dropped, "reader")
    html = render_to_string("library/librarian_picks.html",
                            {"picks": picks, "dropped": dropped, "question": pending["question"]}, request)
    return JsonResponse({"html": html})


@login_required
def ai_key(request):
    """Where a reader keeps their own Gemini key. It is stored by their browser only; this view just shows the page."""
    return render(request, "library/ai_key.html")
