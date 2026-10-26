"""The librarian: recommends up to three books for a question, and only books in the catalog.

The five steps, and the one with a model in it:
1. The question comes in: logged-in readers, at most QUESTION_MAX characters.
2. Retrieval: the CANDIDATES books closest in meaning (pgvector).
3. ★ The model picks up to MAX_PICKS of those, with a reason each. Its answer is JSON whose
   book ids are an enum of the candidates, so the list is closed before it starts writing.
4. Guardrail: code keeps only picks whose id is a candidate and that come with a reason.
   Nothing else reaches the page, and what was dropped is counted.
5. The answer: catalog entries with their reasons, and a log line.

The prompt and the check live here, on the server, whichever key pays for the call: with the
site's key the server calls Gemini; with a reader's own key the browser does, and sends the
model's raw answer back here to be checked.
"""
import json

from pgvector.django import CosineDistance

from .models import Book

CANDIDATES = 12
MAX_PICKS = 3
QUESTION_MAX = 500
SUMMARY_MAX = 600

INSTRUCTIONS = (
    "You are the librarian of Neuralib, a small catalog of public-domain books. Recommend at most "
    f"{MAX_PICKS} books for the reader's question, choosing only from the books listed below, by their id. "
    "For each one, say in one or two sentences why it fits, using only what the list says about it. "
    "If none fits, return an empty list. Write the reasons in the language of the question, "
    "with its usual spelling and accents."
)


def candidates(vector):
    """The books closest in meaning to the question's vector."""
    return list(Book.objects.filter(embedding__isnull=False)
                .annotate(distance=CosineDistance("embedding", vector))
                .order_by("distance")[:CANDIDATES])


def _entry(book):
    summary = book.description if len(book.description) <= SUMMARY_MAX else book.description[:SUMMARY_MAX] + "…"
    lines = [f"id {book.pk}: {book.title}, by {book.writer}"]
    if book.genre:
        lines.append(f"Category: {book.genre}")
    if book.subjects:
        lines.append(f"Subjects: {book.subjects}")
    lines.append(f"Summary: {summary}")
    return "\n".join(lines)


def request_body(question, books):
    """The generateContent request: instructions, the closed list, and a schema whose ids are an enum of it."""
    schema = {
        "type": "OBJECT",
        "properties": {"picks": {"type": "ARRAY", "maxItems": MAX_PICKS, "items": {
            "type": "OBJECT",
            "properties": {"book_id": {"type": "STRING", "enum": [str(b.pk) for b in books]},
                           "reason": {"type": "STRING"}},
            "required": ["book_id", "reason"]}}},
        "required": ["picks"],
    }
    listing = "\n\n".join(_entry(b) for b in books)
    return {
        "systemInstruction": {"parts": [{"text": INSTRUCTIONS}]},
        "contents": [{"role": "user", "parts": [{"text": f"Books:\n\n{listing}\n\nQuestion: {question}"}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": schema, "temperature": 0.2},
    }


def check_picks(model_text, books):
    """Step 4. Returns (picks, dropped): picks are (book, reason) pairs that passed; dropped counts the rest.
    An answer that is not the JSON asked for counts as one dropped."""
    by_id = {str(b.pk): b for b in books}
    try:
        raw = json.loads(model_text).get("picks", [])
        if not isinstance(raw, list):
            raise ValueError
    except (ValueError, AttributeError):
        return [], 1
    picks, seen, dropped = [], set(), 0
    for item in raw:
        book_id = str(item.get("book_id", "")) if isinstance(item, dict) else ""
        reason = item.get("reason", "").strip() if isinstance(item, dict) and isinstance(item.get("reason"), str) else ""
        if book_id in by_id and reason and book_id not in seen and len(picks) < MAX_PICKS:
            picks.append((by_id[book_id], reason))
            seen.add(book_id)
        else:
            dropped += 1
    return picks, dropped
