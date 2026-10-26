"""Text -> vector with Gemini's embedding model, over its REST API.

The key travels in a header, never in the URL. A rate-limit answer is not retried:
the caller hears about it and the page says so, so a busy day cannot turn into a bill.
"""
import hashlib
import json
import urllib.error
import urllib.request

from django.conf import settings
from django.core.cache import cache

DIMENSIONS = 768
BATCH = 50
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"


class EmbeddingError(Exception):
    """The embedding service could not answer (no key, network, bad response)."""


class QuotaExceeded(EmbeddingError):
    """The provider's free quota is used up for now."""


def book_text(book):
    """What a book's vector is made of: what it is called, who wrote it and what it is about."""
    parts = [book.title, book.writer, book.genre, book.subjects, book.description]
    return "\n".join(p for p in parts if p)


def text_hash(text):
    return hashlib.sha256(f"{settings.EMBEDDING_MODEL}:{DIMENSIONS}:{text}".encode()).hexdigest()


def _post(payload):
    if not settings.GEMINI_API_KEY:
        raise EmbeddingError("GEMINI_API_KEY is not set.")
    request = urllib.request.Request(
        API.format(model=settings.EMBEDDING_MODEL),
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": settings.GEMINI_API_KEY},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 429:
            raise QuotaExceeded("The embedding quota is used up for now.") from error
        raise EmbeddingError(f"Embedding request failed with HTTP {error.code}.") from error
    except OSError as error:
        raise EmbeddingError("The embedding service could not be reached.") from error


def embed(texts, task):
    """Vectors for texts. task: RETRIEVAL_DOCUMENT for books, RETRIEVAL_QUERY for searches."""
    model = f"models/{settings.EMBEDDING_MODEL}"
    vectors = []
    for start in range(0, len(texts), BATCH):
        requests = [{"model": model, "content": {"parts": [{"text": t}]}, "taskType": task,
                     "outputDimensionality": DIMENSIONS} for t in texts[start:start + BATCH]]
        answer = _post({"requests": requests})
        batch = [e["values"] for e in answer.get("embeddings", [])]
        if len(batch) != len(requests) or any(len(v) != DIMENSIONS for v in batch):
            raise EmbeddingError("The embedding service returned an unexpected answer.")
        vectors += batch
    return vectors


def _query_key(query):
    return "query-vector:" + text_hash(query.strip().lower())


def cached_query_vector(query):
    """The vector of a search made earlier today, or None. Paging through results does not call the API again."""
    return cache.get(_query_key(query))


def query_vector(query):
    vector = embed([query.strip()], "RETRIEVAL_QUERY")[0]
    cache.set(_query_key(query), vector, 60 * 60 * 24)
    return vector
