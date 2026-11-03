"""Measure the librarian against hand-written questions with known answers (eval/questions.json).

For each question, one call with the whole catalog, as on the site:
- Whether an expected book is among the picks that passed the check, and whether it came with a
  checked quote from its summary or from what the model knows.
- Why picks were dropped: id not in the catalog, no reason, quote not in the summary, repeated
  or over the limit.
- How many tokens the call took, as Gemini reports them.
- Questions with no expected books measure the opposite: the right answer is to pick nothing.

Picks that are not in the expected list are not counted as wrong: the catalog may hold other good
answers. The numbers say whether the expected book was found, not how good every pick was.
"""
import time

from django.conf import settings

from . import librarian
from .gemini import QuotaExceeded, call, generated_text
from .models import Book


def drop_reasons(model_text, books):
    """How many proposed picks were dropped, by reason, in the same order as librarian.check_picks decides."""
    checked = librarian.verdicts(model_text, books)
    if checked is None:
        return {"not_json": 1}
    reasons = {}
    for *_, why in checked:
        if why:
            reasons[why] = reasons.get(why, 0) + 1
    return reasons


def _call_with_patience(body, pause, waits=(60, 120)):
    """One generateContent call for the evaluation: paced, and on a rate limit it waits instead of giving up.
    This is a batch run on a free quota, not a page; the site itself never retries."""
    time.sleep(pause)
    for wait in (*waits, None):
        try:
            return call(settings.LIBRARIAN_MODEL, "generateContent", body)
        except QuotaExceeded:
            if wait is None:
                raise
            time.sleep(wait)


def evaluate(questions, pause=4.0, log=print):
    """Run every question; return per-question results and the totals."""
    books = librarian.catalog()
    by_gutenberg = {b.gutenberg_id: b for b in books if b.gutenberg_id}
    results = []
    for number, q in enumerate(questions, start=1):
        expected = {by_gutenberg[g].pk for g in q["expected"] if g in by_gutenberg}
        answer = _call_with_patience(librarian.request(q["question"], books), pause)
        model_text = generated_text(answer)
        picks, _ = librarian.check_picks(model_text, books)
        usage = answer.get("usageMetadata", {})
        results.append({
            "question": q["question"], "language": q["language"], "kind": q.get("kind"), "expected": sorted(expected),
            "missing_from_catalog": [g for g in q["expected"] if g not in by_gutenberg],
            "quoted_picks": [b.pk for b, _, quote in picks if quote],
            "knowledge_picks": [b.pk for b, _, quote in picks if not quote],
            "proposed": len(librarian.raw_picks(model_text) or []),
            "quotes_proposed": sum(1 for p in librarian.raw_picks(model_text) or []
                                   if isinstance(p, dict) and str(p.get("quote") or "").strip()),
            "drops": drop_reasons(model_text, books),
            "prompt_tokens": usage.get("promptTokenCount"), "cached_tokens": usage.get("cachedContentTokenCount", 0),
            "model_text": model_text,
        })
        found = "yes" if set(results[-1]["quoted_picks"] + results[-1]["knowledge_picks"]) & expected else "-"
        log(f"{number:2d}/{len(questions)} {found:>3}  {q['question'][:70]}")
    return results, totals(results)


def _share(hits, total):
    return {"hits": hits, "of": total, "rate": round(hits / total, 3) if total else None}


def totals(results):
    answerable = [r for r in results if r["expected"]]
    unanswerable = [r for r in results if not r["expected"]]

    def hit(r, key):
        return bool(set(r[key]) & set(r["expected"]))

    out = {"questions": len(results), "answerable": len(answerable), "unanswerable": len(unanswerable),
           "recommends_it": _share(sum(hit(r, "quoted_picks") or hit(r, "knowledge_picks") for r in answerable), len(answerable)),
           "with_a_checked_quote": _share(sum(hit(r, "quoted_picks") for r in answerable), len(answerable)),
           "only_from_knowledge": sum(hit(r, "knowledge_picks") and not hit(r, "quoted_picks") for r in answerable),
           "silent_when_nothing_fits": _share(sum(not r["quoted_picks"] and not r["knowledge_picks"] for r in unanswerable),
                                              len(unanswerable))}
    proposed = sum(r["quotes_proposed"] for r in results)
    bad = sum(r["drops"].get("quote_not_in_summary", 0) for r in results)
    out["quotes_checked"] = {"proposed": proposed, "quote_not_in_summary": bad,
                             "passed_rate": round(1 - bad / proposed, 3) if proposed else None}
    drops = {}
    for r in results:
        for why, n in r["drops"].items():
            drops[why] = drops.get(why, 0) + n
    out["drops"] = drops
    tokens = [r["prompt_tokens"] for r in results if r["prompt_tokens"]]
    out["prompt_tokens_per_question"] = round(sum(tokens) / len(tokens)) if tokens else None
    return out
