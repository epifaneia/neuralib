"""The librarian: recommends books for a question, and only books in the catalog.

Models are used for two things here, in two separate passes over the same question:
- From the summaries: the model reads the summaries of the books closest in meaning and, for
  each pick, copies the excerpt that supports it. Code checks that the excerpt is really in
  that book's summary; a pick whose quote is not there does not reach the page.
- From general knowledge: the model sees only titles and authors of a longer list and answers
  from what it knows about those books (plots, characters, reputation), which may go beyond
  any summary. Code checks the ids; what the model says is shown as its knowledge, unchecked.

The five steps, and where the model is:
1. The question comes in: logged-in readers, at most QUESTION_MAX characters.
2. Retrieval: the books closest in meaning (pgvector).
3. ★ The model picks, twice. Its answers are JSON whose book ids are an enum of the listed
   books, so each list is closed before it starts writing.
4. Guardrail: code keeps only picks whose id was listed, that come with a reason, are not
   repeated, are at most MAX_PICKS and, from the summaries, quote their summary word for word.
   What was dropped is counted.
5. The answer: one card per book with what each pass said, and a log line.

The prompts and the checks live here, on the server, whichever key pays for the calls: with the
site's key the server calls Gemini; with a reader's own key the browser does, and sends the
model's raw answers back here to be checked.
"""
import json
import re

from pgvector.django import CosineDistance

from .models import Book

SUMMARY_CANDIDATES = 12
KNOWLEDGE_CANDIDATES = 40
MAX_PICKS = 3
QUESTION_MAX = 500
SUMMARY_MAX = 600
QUOTE_MIN = 20

_LANGUAGE = "Write in the language of the question, with its usual spelling and accents."
SUMMARY_INSTRUCTIONS = (
    "You are the librarian of Neuralib, a small catalog of public-domain books. Recommend at most "
    f"{MAX_PICKS} books for the reader's question, choosing only from the books listed below, by their id, "
    "and using only what their summaries say. For each one, give the reason in one or two sentences and "
    "copy, word for word, the excerpt of that book's summary that supports it. The reason must say only "
    "what that excerpt says: if a book fits for something its summary does not say, leave it out, because "
    "another pass covers what you know beyond the summaries. If none fits, return an empty list. "
    f"{_LANGUAGE} Copy the excerpt exactly as it is written, in its own language."
)
KNOWLEDGE_INSTRUCTIONS = (
    "You are the librarian of Neuralib, a small catalog of public-domain books. The list below gives only "
    "titles and authors. Using what you know about these books (their plots, characters, settings and "
    f"reputation), recommend at most {MAX_PICKS} for the reader's question, choosing only from the list, "
    "by their id. For each one, say in one or two sentences what you know about it that makes it fit. "
    f"Leave out books you do not know. If none fits, return an empty list. {_LANGUAGE}"
)


def candidates(vector, count):
    """The books closest in meaning to the question's vector."""
    return list(Book.objects.filter(embedding__isnull=False)
                .annotate(distance=CosineDistance("embedding", vector))
                .order_by("distance")[:count])


def _summary(book):
    return book.description if len(book.description) <= SUMMARY_MAX else book.description[:SUMMARY_MAX] + "…"


def _summary_entry(book):
    lines = [f"id {book.pk}: {book.title}, by {book.writer}"]
    if book.genre:
        lines.append(f"Category: {book.genre}")
    if book.subjects:
        lines.append(f"Subjects: {book.subjects}")
    lines.append(f"Summary: {_summary(book)}")
    return "\n".join(lines)


def _body(instructions, listing, question, books, with_quote):
    properties = {"book_id": {"type": "STRING", "enum": [str(b.pk) for b in books]}, "reason": {"type": "STRING"}}
    if with_quote:
        properties["quote"] = {"type": "STRING"}
    schema = {
        "type": "OBJECT",
        "properties": {"picks": {"type": "ARRAY", "maxItems": MAX_PICKS, "items": {
            "type": "OBJECT", "properties": properties, "required": list(properties)}}},
        "required": ["picks"],
    }
    return {
        "systemInstruction": {"parts": [{"text": instructions}]},
        "contents": [{"role": "user", "parts": [{"text": f"Books:\n\n{listing}\n\nQuestion: {question}"}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": schema, "temperature": 0.2},
    }


def summary_request(question, books):
    """Pass 1: the summaries, and an excerpt of the right one for each pick."""
    listing = "\n\n".join(_summary_entry(b) for b in books)
    return _body(SUMMARY_INSTRUCTIONS, listing, question, books, with_quote=True)


def knowledge_request(question, books):
    """Pass 2: titles and authors only; the model answers from what it knows."""
    listing = "\n".join(f"id {b.pk}: {b.title}, by {b.writer}" for b in books)
    return _body(KNOWLEDGE_INSTRUCTIONS, listing, question, books, with_quote=False)


_QUOTE_MARKS = str.maketrans({"“": '"', "”": '"', "«": '"', "»": '"', "‘": "'", "’": "'", "—": "-", "–": "-"})


def _normalize(text):
    text = text.translate(_QUOTE_MARKS).replace("…", "...").lower()
    return re.sub(r"\s+", " ", text).strip()


def quote_in_summary(quote, summary):
    """True when the quote, give or take case, spacing, quote marks and the dots around it, is in the summary."""
    quote = _normalize(quote).strip(" .\"'-")
    return len(quote) >= QUOTE_MIN and quote in _normalize(summary)


def _check(model_text, books, with_quote):
    """Picks that pass, and how many were dropped. An answer that is not the JSON asked for counts as one dropped."""
    by_id = {str(b.pk): b for b in books}
    try:
        raw = json.loads(model_text).get("picks", [])
        if not isinstance(raw, list):
            raise ValueError
    except (ValueError, AttributeError):
        return [], 1
    picks, seen, dropped = [], set(), 0
    for item in raw:
        item = item if isinstance(item, dict) else {}
        book_id = str(item.get("book_id", ""))
        reason = item.get("reason").strip() if isinstance(item.get("reason"), str) else ""
        quote = item.get("quote").strip() if isinstance(item.get("quote"), str) else ""
        book = by_id.get(book_id)
        quoted = not with_quote or (book is not None and quote_in_summary(quote, book.description))
        if book and reason and quoted and book_id not in seen and len(picks) < MAX_PICKS:
            picks.append((book, reason, quote) if with_quote else (book, reason))
            seen.add(book_id)
        else:
            dropped += 1
    return picks, dropped


def check_summary_picks(model_text, books):
    """Pass 1 → ([(book, reason, quote)], dropped)."""
    return _check(model_text, books, with_quote=True)


def check_knowledge_picks(model_text, books):
    """Pass 2 → ([(book, reason)], dropped)."""
    return _check(model_text, books, with_quote=False)


def cards(summary_picks, knowledge_picks):
    """One card per book: what both passes agree on first, then the summaries' picks, then the knowledge's."""
    known = {book.pk: reason for book, reason in knowledge_picks}
    result = [{"book": book, "reason": reason, "quote": quote, "knowledge": known.get(book.pk)}
              for book, reason, quote in summary_picks]
    result.sort(key=lambda card: card["knowledge"] is None)
    from_summaries = {card["book"].pk for card in result}
    result += [{"book": book, "reason": None, "quote": None, "knowledge": reason}
               for book, reason in knowledge_picks if book.pk not in from_summaries]
    return result
