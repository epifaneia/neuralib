"""The librarian: recommends books for a question, and only books in the catalog.

The whole catalog fits in the model's context (about 300 books, each summary cut to SUMMARY_MAX
characters), so nothing is retrieved: the model reads every book and answers in one call. For each
pick it says where its reason comes from:
- From the summary: it copies, word for word, the excerpt that supports it. Code checks that the
  excerpt is really in that book's summary; a pick whose quote is not there does not reach the page.
- From what it knows about the book (plot, ending, length, reputation) beyond its summary: no
  quote. Code checks the id; what the model says is shown as its knowledge, unchecked.

The five steps, and where the model is:
1. The question comes in: logged-in readers, at most QUESTION_MAX characters.
2. Context: the whole catalog, by code, always in the same order. If the catalog outgrew the
   context, this is where a search would come back in.
3. The answer is JSON whose book ids are an enum of the catalog, so the list is closed before
   the model starts writing.
4. ★ The model picks, once.
5. Guardrail: code keeps only picks whose id is in the catalog, that come with a reason, are not
   repeated, are at most MAX_PICKS and, when they quote, quote their summary word for word.
   What was dropped is counted.

The prompt and the checks live here, on the server, whichever key pays for the call: with the
site's key the server calls Gemini; with a reader's own key the browser does, and sends the
model's raw answer back here to be checked.
"""
import json
import re

from .models import Book

MAX_PICKS = 3
QUESTION_MAX = 500
SUMMARY_MAX = 600
QUOTE_MIN = 20

INSTRUCTIONS = (
    "You are the librarian of Neuralib, a small catalog of public-domain books. Recommend at most "
    f"{MAX_PICKS} books for the reader's question, choosing only from the books listed below, by their id. "
    "For each one, give the reason in one or two sentences, and say where it comes from. If the book's "
    "summary says why it fits, copy in `quote`, word for word, the excerpt of that summary that says it "
    "(a phrase or a sentence of the summary, never just the title), "
    "and let the reason say only what that excerpt says. If it fits for something you know about the book "
    "that its summary does not say (its plot, its ending, its length, its reputation), leave `quote` empty "
    "and say in the reason what you know. Leave out books you do not know. If none fits, return an empty "
    "list. Write in the language of the question, with its usual spelling and accents. Copy an excerpt "
    "exactly as it is written, in its own language."
)


def catalog():
    """Every book, always in the same order: the model's whole context."""
    return list(Book.objects.order_by("pk"))


def _summary(book):
    return book.description if len(book.description) <= SUMMARY_MAX else book.description[:SUMMARY_MAX] + "…"


def _entry(book):
    lines = [f"id {book.pk}: {book.title}, by {book.writer}"]
    if book.genre:
        lines.append(f"Category: {book.genre}")
    if book.subjects:
        lines.append(f"Subjects: {book.subjects}")
    lines.append(f"Summary: {_summary(book)}")
    return "\n".join(lines)


def request(question, books):
    """The generateContent body: the instructions, the catalog first and the question last."""
    item = {"type": "OBJECT",
            "properties": {"book_id": {"type": "STRING", "enum": [str(b.pk) for b in books]},
                           "reason": {"type": "STRING"}, "quote": {"type": "STRING"}},
            "required": ["book_id", "reason", "quote"]}
    schema = {"type": "OBJECT", "properties": {"picks": {"type": "ARRAY", "maxItems": MAX_PICKS, "items": item}},
              "required": ["picks"]}
    listing = "\n\n".join(_entry(b) for b in books)
    return {
        "systemInstruction": {"parts": [{"text": INSTRUCTIONS}]},
        "contents": [{"role": "user", "parts": [{"text": f"Books:\n\n{listing}\n\nQuestion: {question}"}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": schema, "temperature": 0.2},
    }


# Quotation marks do not count: Gutenberg's summaries open with the title in quotes, and a model copying
# that line often leaves them out. Apostrophes stay, they are part of words.
_QUOTE_MARKS = str.maketrans({"“": None, "”": None, "«": None, "»": None, '"': None,
                              "‘": "'", "’": "'", "—": "-", "–": "-"})


def _normalize(text):
    text = text.translate(_QUOTE_MARKS).replace("…", "...").lower()
    return re.sub(r"\s+", " ", text).strip()


def quote_in_summary(quote, summary):
    """True when the quote, give or take case, spacing, quotation marks and the dots around it, is in the summary."""
    quote = _normalize(quote).strip(" .\"'-")
    return len(quote) >= QUOTE_MIN and quote in _normalize(summary)


def raw_picks(model_text):
    """The list of picks the model proposed, or None if its answer is not the JSON asked for."""
    try:
        picks = json.loads(model_text).get("picks", [])
    except (ValueError, AttributeError):
        return None
    return picks if isinstance(picks, list) else None


def verdicts(model_text, books):
    """Each proposed pick with what the check makes of it: (item, book, reason, quote, why_dropped or None)."""
    raw = raw_picks(model_text)
    if raw is None:
        return None
    by_id, seen, kept, out = {str(b.pk): b for b in books}, set(), 0, []
    for item in raw:
        item = item if isinstance(item, dict) else {}
        book = by_id.get(str(item.get("book_id", "")))
        reason = item.get("reason").strip() if isinstance(item.get("reason"), str) else ""
        quote = item.get("quote").strip() if isinstance(item.get("quote"), str) else ""
        if book is None:
            why = "not_listed"
        elif not reason:
            why = "no_reason"
        elif quote and not quote_in_summary(quote, book.description):
            why = "quote_not_in_summary"
        elif book.pk in seen:
            why = "repeated"
        elif kept >= MAX_PICKS:
            why = "over_limit"
        else:
            why = None
            seen.add(book.pk)
            kept += 1
        out.append((book, reason, quote, why))
    return out


def check_picks(model_text, books):
    """([(book, reason, quote or None)], dropped). An answer that is not the JSON asked for counts as one dropped."""
    checked = verdicts(model_text, books)
    if checked is None:
        return [], 1
    picks = [(book, reason, quote or None) for book, reason, quote, why in checked if why is None]
    return picks, len(checked) - len(picks)


def cards(picks):
    """One card per book, in the model's order; a card without a quote is the model's knowledge."""
    return [{"book": book, "reason": reason, "quote": quote} for book, reason, quote in picks]
