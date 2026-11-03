# Neuralib · a library with a librarian

*Read this in [Español](README.es.md).*

**Live: [neuralib-m8q6.onrender.com](https://neuralib-m8q6.onrender.com)** (free plan: the first visit after a quiet spell takes about a minute to wake up).

A catalog of 300 public-domain books (Project Gutenberg, in Spanish and English), and one that is not, with a keyword search and a librarian that recommends in plain language. The librarian reads the whole catalog and answers only with books in it: when a book's summary says why it fits, it quotes the line, and code checks the quote exists; when it fits for what the model knows about the book beyond its summary, the answer says so. It is a 2023 bootcamp project, rescued and rewritten in 2026; the repository's history tells how.

> AI carries risk. Code bounds it. The standard answers for what remains.

[Design philosophy](#design-philosophy) · [Where AI adds value](#where-ai-adds-value) · [The whole catalog, not a search](#the-whole-catalog-not-a-search) · [The five steps](#the-five-steps-in-this-project) · [Measured](#measured) · [Try it](#try-it-locally) · [Limitations](#limitations) · [Security and regulation](#security-and-regulation)

---

## Design philosophy

Every AI application has five steps. Only one decides with a model; the rest are code: reproducible, testable, offline. Step 5 never corrects: it flags and drops. Full text at [epifaneia.dev](https://epifaneia.dev).

```
 1 CLEANING      2 CONTEXT       3 INPUT GUARDRAIL   4 PROCESS        5 OUTPUT GUARDRAIL
 ■ code          ■ code          ■ code              ▲ model          ■ code
```

There is one model here, in step 4: a language model (`gemini-3.5-flash-lite`) that picks and explains. Everything it says goes through step 5.

## Where AI adds value

A reader does not search "title contains X": they ask for "something to make me laugh", "a love story with a happy ending", "something short I can finish in one sitting". No keyword search answers that, and that is why the catalog's search box stays a keyword search: meaning is the librarian's job. The model brings two different things: reading (relating the question to what the summaries say) and knowing (the plots, authors and reputation of books the world has been reading for centuries). Both come in the same answer, and each pick says which one it is: a quote from its summary, checked, or the model's knowledge, labelled. Code keeps everything else: which books exist, which quote is real, what is shown and what is dropped.

## The whole catalog, not a search

Until 3 November the librarian worked like a textbook RAG: an embedding model ordered the catalog by closeness of meaning, pgvector stored the vectors, and two calls read the 12 and the 40 closest books. Then it went back to the first idea, the simplest one: give the model the whole catalog. 301 books with their summaries cut to 600 characters are about 53,000 tokens, which a current model reads in one call. It is the same rule as in [ctsm](https://github.com/epifaneia/ctsm) and [toolkit](https://github.com/epifaneia/toolkit): the whole corpus when it fits, a search only when it does not. The vector version stays in the history, and [Measured](#measured) compares the two.

---

## The five steps in this project

★ marks where the improvement is in this project: the **input** and the **output guardrails**.

| Step | What it does here | |
|---|---|---|
| 1 · Cleaning | `import_gutenberg` brings in the most downloaded books per language from the public Gutendex API: it skips books still under copyright, non-text media and books without a summary; cleans titles of leftover catalog codes (`$b`, `::`); flags automatically generated summaries. Running it again updates, never duplicates. | |
| 2 · Context | The whole catalog in every question, always in the same order: id, title, author, category, subjects and the summary cut to 600 characters, about 53,000 tokens. Nothing is retrieved: with 301 books there is nothing to leave out. If the catalog outgrew the model's context, this is where a search would come back in. The search box is plain keywords: title, writer, summary, subject, category, language or ISBN. | |
| 3 · Input guardrail | The answer is JSON with a schema whose `book_id` is an enum of the catalog's ids: naming a book outside it is structurally impossible. Each pick carries a `quote`, word for word from its summary, or empty when the reason is the model's knowledge. Questions are capped at 500 characters and to signed-in readers. | ★ |
| 4 · Process | One call per question: "if the summary says why it fits, copy the excerpt that says it (a phrase or a sentence, never just the title); if it fits for what you know beyond the summary, leave the quote empty and say what you know; leave out books you do not know". | |
| 5 · Output guardrail | `librarian.check_picks` drops: an id not in the catalog, an empty reason, a repeat, more than three, and a quote that is not word for word in that book's summary (case, spacing, quotation marks and dots aside; at least 20 characters). The page says how many were dropped. A pick without a quote is shown as the model's knowledge, unchecked. | ★ |

## Measured

Two sets of questions written for this measurement (not by the model under test), with the books that should come out, by Gutenberg id: [`eval/questions.json`](eval/questions.json) and [`eval/questions_hard.json`](eval/questions_hard.json). `python manage.py evaluate` reproduces the tables and keeps the raw answers in [`eval/results/`](eval/results/). Measured on 3-11-2026 over the 301 books.

**Base set, 36 questions** that describe the plot without the title; Spanish questions for books only in English and the other way round; 2 with no answer in the catalog.

| What | Result |
|---|---|
| Recommends the expected book | 34 / 34 |
| … with a checked quote from its summary | 34 / 34 |
| No answer in the catalog: recommends nothing | 2 / 2 |
| Quotes that pass the check | 41 / 42 |
| Tokens per question | about 53,000 |

**Hard set, 18 questions** of three kinds: *knowledge* (the answer needs a fact no summary has: Lepanto, The Raven, Colliure), *mood* (several right answers, a matter of taste) and *trap* (negations, misleading words, nothing in the catalog).

| Kind | Recommends it | With a checked quote | Only from knowledge | Silent when nothing fits |
|---|---|---|---|---|
| Knowledge (7) | 7 / 7 | 4 / 7 | 3 | — |
| Mood (5) | 4 / 5 | 4 / 5 | 0 | — |
| Trap (6) | 3 / 4 | 2 / 4 | 1 | 2 / 2 |

**Against the vector version**, the same 54 questions:

| | Vector search and two passes (28-10-2026) | Whole catalog, one call (3-11-2026) |
|---|---|---|
| Calls per question | 3: one embedding, two generations | 1 |
| Tokens per question | about 3,500 (estimated; the October runs did not count them) | about 53,000 |
| Recommends the expected book (50 questions) | 50 / 50 | 48 / 50 |
| Mood questions with a checked quote | 3 / 5 | 4 / 5 |
| Silent when nothing fits | 4 / 4 | 4 / 4 |
| Quotes that pass the check | 64 / 65 | 56 / 63 |

What follows from those tables. The single call finds the expected book in 48 of 50, and which two it misses changes from run to run: a first run, before two fixes (quotation marks no longer count in the check; the instruction asks for a passage, not the title), missed *Lazarillo* and Latin American poetry; this one misses "something short" (it offered *Jekyll*, short too, but not on the list) and "a book about the sea that is not an adventure novel". With sets this small that is noise, not a difference. What does change: mood questions, which search ranked badly (the expected short book came 26th), now mostly come with a checked quote, because the model sees every book. And the model quotes worse with 301 books in front of it: sometimes it copies a subject heading (*Saint Petersburg (Russia) -- Fiction*), a bare title or a sentence it translated into the question's language. The check drops every one of those, and none reaches the reader. The price is the context: about 15 times more tokens per question, which on Gemini's free quota costs nothing.

## Try it locally

You need Postgres with the pgvector extension available, because an early migration, from the vector version, still creates it: [Neon](https://neon.com)'s free plan has it (use the direct connection, not the pooled one). The Gemini key is optional; better from a project without billing, so nothing can be charged.

```bash
python -m venv .venv && .venv/Scripts/activate    # on Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                              # DATABASE_URL and, if you want, GEMINI_API_KEY
python manage.py migrate
python manage.py import_gutenberg                 # 150 books in Spanish and 150 in English
python manage.py add_nogum                        # the one that is not public domain
python manage.py runserver
python manage.py test                             # 72 tests, never calling Gemini or Gutenberg
python manage.py evaluate --questions eval/questions_hard.json
```

The catalog needs no key: its search is by keyword. Without `GEMINI_API_KEY` the librarian asks each reader for their own key (the "AI key" page): it is kept by their browser, and their browser is what talks to Google.

**Heroku.** `Procfile` with `release: migrate` and gunicorn; WhiteNoise serves static files. Set `DATABASE_URL`, `SECRET_KEY` and, if the site should answer with its own key, `GEMINI_API_KEY` as config vars. In production the site requires HTTPS, secure cookies and HSTS, and does not start without `SECRET_KEY`.

**Render.** `render.yaml` is a blueprint for a free web service: it installs, collects static files, migrates and starts gunicorn, and generates `SECRET_KEY`. Paste `DATABASE_URL` (Neon) and, optionally, `GEMINI_API_KEY` when it asks. The free plan sleeps after a while without visits, so the first request after that takes about a minute.

## Limitations

- **A checked quote is not a checked reason.** Code guarantees the quote exists in that book's summary, not that it says what the reason says: a reason can add to a real quote what the model knows (where an author lived, where he died). Checking it would take another model as judge, and that is no longer code checking.
- A pick without a quote cannot be checked: what the model knows about a book is shown as its own, labelled, and it can be wrong.
- The summaries are generated automatically by Project Gutenberg (285 of 300) and are in English; the site says so on each entry. So quotes come out in English even when the question is in Spanish, and when the model translates one, the check drops it.
- The whole catalog goes into every question. It fits today; with a few thousand books it would not, and a search would have to choose what the model reads.
- The sets are small (54 questions) and the mood questions have answers of taste: read them as a smoke test, not a benchmark. On the base set, which does not tell things apart, everything is close to 100%.
- The daily caps live in the process's local cache: enough with one dyno; with several, each would count on its own.
- Some books are in the catalog twice, once per language (*Treasure Island* and *La isla del tesoro*); the librarian may recommend both.

---

## Security and regulation

The same four headings in every repository. **today** rows are what the code does. This repository does not carry the three integration wires (identity, events, sign-off) of [toolkit](https://github.com/epifaneia/toolkit): it is a public demo over public-domain books, with no confidential data to keep.

| | | |
|---|---|---|
| **Confidentiality** | The site's key lives only in `.env` or in the config vars, never in git, and travels to Google in a header, never in the URL. A reader's key lives only in their browser (forgotten when the tab closes unless they ask to keep it) and never reaches the server. What goes to Google is the question and the catalog (titles, authors and summaries of public-domain books); the page says so. In the EEA, Switzerland and the UK, Gemini's terms apply the paid-service conditions to the free quota: what is sent is not used to improve their products. | **today** |
| **Traceability** | Every librarian answer is kept in `LibrarianAnswer`: the question, the books recommended with a checked quote and those from the model's knowledge, the drops, the model and whose key paid. Not the reader. Read-only in the admin. Measurements keep the model's raw answers. | **today** |
| **Leak prevention** | The model has no credentials and no access to the database: it only sees the catalog it is given, and can only answer with its ids. With a reader's key the server never makes the call: it prepares the request, checks the raw answer with a one-use token tied to that reader, and nothing else. | **today** |
| **Human in the loop** | The librarian recommends; the reader decides. Each recommendation says whether it comes from the summary, with its quote, or from the model's knowledge, and the page says how many suggestions were dropped and why. If nothing fits, it says so. | **today** |

Framework: EU AI Act (2024/1689) · GDPR.

---

## Structure

```
library/     models · views · librarian (the request with the whole catalog, and its checks) · quota · gemini
             gutenberg (import) · evaluation · management/commands/ (import_gutenberg · add_nogum · evaluate)
             templates/ · static/library/librarian.js (the reader's key, in the browser only) · tests/ (72 tests)
eval/        questions.json · questions_hard.json · results/ (every measurement, with the raw answers)
django_library/  settings (local and Heroku in one file) · urls
.github/workflows/tests.yml   the tests against Postgres 17 with pgvector on every push
```

Daniel Martín · [epifaneia.dev](https://epifaneia.dev) · Apache-2.0
