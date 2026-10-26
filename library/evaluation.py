"""Measure search and the librarian against hand-written questions with known answers (eval/questions.json).

For each question:
- Search: where the first expected book ranks among the closest in meaning (hit@5, @12, @40).
- Each librarian pass: whether an expected book is among its picks, and why picks were dropped:
  id not listed, no reason, quote not in the summary (first pass), repeated or over the limit.
- Questions with no expected books measure the opposite: the right answer is to pick nothing.

Picks that are not in the expected list are not counted as wrong: the catalog may hold other good
answers. The numbers say whether the expected book was found, not how good every pick was.
"""
import json
import time

from django.conf import settings

from . import librarian
from .embeddings import embed
from .gemini import QuotaExceeded, call, generated_text
from .models import Book


def _raw_picks(model_text):
    try:
        picks = json.loads(model_text).get("picks", [])
        return picks if isinstance(picks, list) else None
    except (ValueError, AttributeError):
        return None


def drop_reasons(model_text, books, with_quote):
    """Why each proposed pick did or did not pass, in the same order as librarian._check decides."""
    raw = _raw_picks(model_text)
    if raw is None:
        return {"not_json": 1}
    by_id, seen, kept, reasons = {str(b.pk): b for b in books}, set(), 0, {}
    for item in raw:
        item = item if isinstance(item, dict) else {}
        book = by_id.get(str(item.get("book_id", "")))
        reason = item.get("reason").strip() if isinstance(item.get("reason"), str) else ""
        quote = item.get("quote").strip() if isinstance(item.get("quote"), str) else ""
        if book is None:
            why = "not_listed"
        elif not reason:
            why = "no_reason"
        elif with_quote and not librarian.quote_in_summary(quote, book.description):
            why = "quote_not_in_summary"
        elif book.pk in seen:
            why = "repeated"
        elif kept >= librarian.MAX_PICKS:
            why = "over_limit"
        else:
            seen.add(book.pk)
            kept += 1
            continue
        reasons[why] = reasons.get(why, 0) + 1
    return reasons


def _call_with_patience(body, pause, waits=(60, 120)):
    """One generateContent call for the evaluation: paced, and on a rate limit it waits instead of giving up.
    This is a batch run on a free quota, not a page; the site itself never retries."""
    time.sleep(pause)
    for wait in (*waits, None):
        try:
            return generated_text(call(settings.LIBRARIAN_MODEL, "generateContent", body))
        except QuotaExceeded:
            if wait is None:
                raise
            time.sleep(wait)


def evaluate(questions, retrieval_only=False, pause=4.0, log=print):
    """Run every question; return per-question results and the totals."""
    by_gutenberg = {b.gutenberg_id: b for b in Book.objects.exclude(gutenberg_id=None)}
    vectors = embed([q["question"] for q in questions], "RETRIEVAL_QUERY")
    results = []
    for number, (q, vector) in enumerate(zip(questions, vectors), start=1):
        expected = {by_gutenberg[g].pk for g in q["expected"] if g in by_gutenberg}
        missing = [g for g in q["expected"] if g not in by_gutenberg]
        ranked = librarian.candidates(vector, librarian.KNOWLEDGE_CANDIDATES)
        rank = next((i for i, b in enumerate(ranked, start=1) if b.pk in expected), None)
        row = {"question": q["question"], "language": q["language"], "expected": sorted(expected),
               "missing_from_catalog": missing, "first_expected_rank": rank}
        if not retrieval_only:
            summary_books = ranked[:librarian.SUMMARY_CANDIDATES]
            summary_text = _call_with_patience(librarian.summary_request(q["question"], summary_books), pause)
            knowledge_text = _call_with_patience(librarian.knowledge_request(q["question"], ranked), pause)
            summary_picks, _ = librarian.check_summary_picks(summary_text, summary_books)
            knowledge_picks, _ = librarian.check_knowledge_picks(knowledge_text, ranked)
            raw_summary = _raw_picks(summary_text) or []
            row.update(
                summary_picks=[b.pk for b, _, _ in summary_picks],
                knowledge_picks=[b.pk for b, _ in knowledge_picks],
                summary_proposed=len(raw_summary),
                summary_drops=drop_reasons(summary_text, summary_books, with_quote=True),
                knowledge_drops=drop_reasons(knowledge_text, ranked, with_quote=False),
                summary_text=summary_text, knowledge_text=knowledge_text,
            )
        results.append(row)
        log(f"{number:2d}/{len(questions)} rank {rank or '-':>2}  {q['question'][:70]}")
    return results, totals(results)


def _share(hits, total):
    return {"hits": hits, "of": total, "rate": round(hits / total, 3) if total else None}


def totals(results):
    answerable = [r for r in results if r["expected"]]
    unanswerable = [r for r in results if not r["expected"]]
    out = {"questions": len(results), "answerable": len(answerable), "unanswerable": len(unanswerable)}
    for k in (5, librarian.SUMMARY_CANDIDATES, librarian.KNOWLEDGE_CANDIDATES):
        out[f"search_hit_at_{k}"] = _share(sum(1 for r in answerable if r["first_expected_rank"] and r["first_expected_rank"] <= k), len(answerable))
    ranks = [r["first_expected_rank"] for r in answerable]
    out["search_mrr_at_40"] = round(sum(1 / r for r in ranks if r) / len(answerable), 3) if answerable else None
    if results and "summary_picks" in results[0]:
        def hit(r, key):
            return bool(set(r[key]) & set(r["expected"]))
        out["summary_pass_hit"] = _share(sum(hit(r, "summary_picks") for r in answerable), len(answerable))
        out["knowledge_pass_hit"] = _share(sum(hit(r, "knowledge_picks") for r in answerable), len(answerable))
        out["either_pass_hit"] = _share(sum(hit(r, "summary_picks") or hit(r, "knowledge_picks") for r in answerable), len(answerable))
        out["knowledge_only_hit"] = sum(hit(r, "knowledge_picks") and not hit(r, "summary_picks") for r in answerable)
        out["summary_pass_abstained"] = _share(sum(not r["summary_picks"] for r in unanswerable), len(unanswerable))
        out["knowledge_pass_abstained"] = _share(sum(not r["knowledge_picks"] for r in unanswerable), len(unanswerable))
        proposed = sum(r["summary_proposed"] for r in results)
        bad_quotes = sum(r["summary_drops"].get("quote_not_in_summary", 0) for r in results)
        out["quotes_checked"] = {"proposed": proposed, "quote_not_in_summary": bad_quotes,
                                 "passed_rate": round(1 - bad_quotes / proposed, 3) if proposed else None}
        drops = {}
        for r in results:
            for side in ("summary_drops", "knowledge_drops"):
                for why, n in r[side].items():
                    drops[f"{side.split('_')[0]}:{why}"] = drops.get(f"{side.split('_')[0]}:{why}", 0) + n
        out["drops"] = drops
    return out
