"""Semantic search: the books whose meaning is closest to a question, with pgvector."""
from datetime import date

from django.conf import settings
from django.core.cache import cache
from pgvector.django import CosineDistance

from .embeddings import EmbeddingError, cached_query_vector, query_vector
from .models import Book

RESULTS = 20


class SearchLimitReached(EmbeddingError):
    """Today's share of the free quota is spent, for this visitor or for everyone."""


def _visitor(request):
    if request.user.is_authenticated:
        return f"user-{request.user.pk}"
    # Behind Heroku's router the visitor's address is the first one in X-Forwarded-For.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return "ip-" + (forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR", "unknown"))


def _spend_one(request):
    """Count one call against today's caps; False when either cap is already reached."""
    today = date.today().isoformat()
    counters = [(f"semantic:{today}:all", settings.SEMANTIC_SEARCHES_PER_DAY),
                (f"semantic:{today}:{_visitor(request)}", settings.SEMANTIC_SEARCHES_PER_VISITOR_PER_DAY)]
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
        if not _spend_one(request):
            raise SearchLimitReached("Today's AI searches are used up.")
        vector = query_vector(query)
    return list(Book.objects.filter(embedding__isnull=False)
                .annotate(distance=CosineDistance("embedding", vector))
                .order_by("distance")[:RESULTS])
