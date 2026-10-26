"""Semantic search: the books whose meaning is closest to a question, with pgvector."""
from datetime import date

from django.conf import settings
from django.core.cache import cache
from pgvector.django import CosineDistance

from .embeddings import cached_query_vector, query_vector
from .gemini import GeminiError
from .models import Book

RESULTS = 20


class SearchLimitReached(GeminiError):
    """Today's share of the free quota is spent, for this visitor or for everyone."""


def _visitor(request):
    if request.user.is_authenticated:
        return f"user-{request.user.pk}"
    # Behind Heroku's router the visitor's address is the first one in X-Forwarded-For.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return "ip-" + (forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR", "unknown"))


def spend_one(request, name, per_visitor, overall):
    """Count one call to the site's key against today's caps; False when either cap is already reached."""
    today = date.today().isoformat()
    counters = [(f"{name}:{today}:all", overall), (f"{name}:{today}:{_visitor(request)}", per_visitor)]
    if any(cache.get(key, 0) >= limit for key, limit in counters):
        return False
    for key, _ in counters:
        cache.add(key, 0, 60 * 60 * 26)
        cache.incr(key)
    return True


def semantic_search(request, query):
    """Up to RESULTS books, closest in meaning first. A search already made today costs nothing."""
    vector = cached_query_vector(query)
    if vector is None:
        if not spend_one(request, "semantic", settings.SEMANTIC_SEARCHES_PER_VISITOR_PER_DAY,
                         settings.SEMANTIC_SEARCHES_PER_DAY):
            raise SearchLimitReached("Today's AI searches are used up.")
        vector = query_vector(query)
    return list(Book.objects.filter(embedding__isnull=False)
                .annotate(distance=CosineDistance("embedding", vector))
                .order_by("distance")[:RESULTS])
