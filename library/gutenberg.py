"""Project Gutenberg books, through the public Gutendex API (https://gutendex.com)."""
import json
import re
import time
import urllib.request

GUTENDEX = "https://gutendex.com/books/"
GENERATED_NOTE = "(This is an automatically generated summary.)"


def fetch_json(url, attempts=3):
    """GET a Gutendex page. Gutendex is slow at times, so retry before giving up."""
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Neuralib catalog import"})
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except OSError:
            if attempt == attempts:
                raise
            time.sleep(2 * attempt)


def author_name(author):
    """'Dostoyevsky, Fyodor' -> 'Fyodor Dostoyevsky'. Other shapes stay as they are."""
    parts = [p.strip() for p in author["name"].split(",")]
    return f"{parts[1]} {parts[0]}" if len(parts) == 2 else author["name"]


def book_fields(item):
    """Map one Gutendex result to Book fields, or None if it cannot be a catalog entry
    (still under copyright, not a text, or without a summary to search on)."""
    summaries = [s for s in item.get("summaries") or [] if s.strip()]
    if item.get("copyright") or item.get("media_type") != "Text" or not summaries:
        return None
    summary = summaries[0].strip()
    generated = GENERATED_NOTE in summary
    categories = [s.removeprefix("Category: ") for s in item.get("bookshelves", []) if s.startswith("Category: ")]
    formats = item.get("formats", {})
    title = re.sub(r"\s+", " ", item["title"]).strip()
    # Some titles keep library catalog subfield codes: "Boston : $b a novel" -> "Boston: a novel".
    title = re.sub(r"(\s*:)*\s*\$[a-z]\s+", ": ", title)
    title = re.sub(r"\s*:{2,}", ":", title)
    return {
        "title": title[:200],
        "description": summary.replace(GENERATED_NOTE, "").strip(),
        "summary_is_generated": generated,
        "genre": " · ".join(categories)[:200],
        "subjects": "; ".join(item.get("subjects", [])),
        "language": (item.get("languages") or [""])[0],
        "writer": (", ".join(author_name(a) for a in item.get("authors", [])) or "Anonymous")[:200],
        "image_url": formats.get("image/jpeg"),
        "read_online": formats.get("text/html") or f"https://www.gutenberg.org/ebooks/{item['id']}",
        "download_link": formats.get("application/epub+zip"),
    }


def popular_books(language, count):
    """Yield (gutenberg_id, fields) for the most downloaded books in a language, up to count."""
    url, found = f"{GUTENDEX}?languages={language}", 0
    while url and found < count:
        page = fetch_json(url)
        for item in page["results"]:
            fields = book_fields(item)
            if fields and fields["language"] == language:
                yield item["id"], fields
                found += 1
                if found == count:
                    return
        url = page.get("next")
