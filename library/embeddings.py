"""Text -> vector with Gemini's embedding model."""
import hashlib

from django.conf import settings
from django.core.cache import cache

from .gemini import GeminiError, call

DIMENSIONS = 768
BATCH = 50


def book_text(book):
    """What a book's vector is made of: what it is called, who wrote it and what it is about."""
    parts = [book.title, book.writer, book.genre, book.subjects, book.description]
    return "\n".join(p for p in parts if p)


def text_hash(text):
    return hashlib.sha256(f"{settings.EMBEDDING_MODEL}:{DIMENSIONS}:{text}".encode()).hexdigest()


def embed(texts, task):
    """Vectors for texts. task: RETRIEVAL_DOCUMENT for books, RETRIEVAL_QUERY for searches."""
    model = f"models/{settings.EMBEDDING_MODEL}"
    vectors = []
    for start in range(0, len(texts), BATCH):
        requests = [{"model": model, "content": {"parts": [{"text": t}]}, "taskType": task,
                     "outputDimensionality": DIMENSIONS} for t in texts[start:start + BATCH]]
        answer = call(settings.EMBEDDING_MODEL, "batchEmbedContents", {"requests": requests})
        batch = [e["values"] for e in answer.get("embeddings", [])]
        if len(batch) != len(requests) or any(len(v) != DIMENSIONS for v in batch):
            raise GeminiError("The embedding service returned an unexpected answer.")
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
