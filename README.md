# Neuralib · a library with a librarian

*Read this in [Español](README.es.md).*

A catalog of 300 public-domain books (Project Gutenberg, in Spanish and English) with search by meaning and a librarian that recommends in plain language. The librarian answers twice, and only with books in the catalog: once from the summaries, quoting the line that backs each recommendation (code checks the quote exists), and once from what the model knows about those books, labelled as such. It is a 2023 bootcamp project, rescued and rewritten in 2026; the repository's history tells how.

> AI carries risk. Code bounds it. The standard answers for what remains.

[Design philosophy](#design-philosophy) · [Where AI adds value](#where-ai-adds-value) · [The five steps](#the-five-steps-in-this-project) · [Measured](#measured) · [Try it](#try-it-locally) · [Limitations](#limitations) · [Security and regulation](#security-and-regulation)

---

## Design philosophy

Every AI application has five steps. Only one decides with a model; the rest are code: reproducible, testable, offline. Step 5 never corrects: it flags and drops. Full text at [epifaneia.dev](https://epifaneia.dev).

```
 1 CLEANING      2 CONTEXT       3 INPUT GUARDRAIL   4 PROCESS        5 OUTPUT GUARDRAIL
 ■ code          ■ code + ▲      ■ code              ▲ model          ■ code
```

There are two models here, and it is worth saying where. In step 2 an embedding model (`gemini-embedding-001`) only orders the catalog by closeness of meaning; it writes nothing. In step 4 a language model (`gemini-3.5-flash-lite`) picks and explains, and everything it says goes through step 5.

## Where AI adds value

A reader does not search "title contains X": they ask for "something to make me laugh", "a love story with a happy ending", "something short I can finish in one sitting". No keyword search answers that, and no summary says how long a book is or how it ends. The model brings two different things, which is why there are two passes: reading (relating the question to what the summaries say) and knowing (the plots, authors and reputation of books the world has been reading for centuries). Code keeps everything else: which books exist, which quote is real, what is shown and what is dropped.

---

## The five steps in this project

★ marks where the improvement is in this project: the **input** and the **output guardrails**.

| Step | What it does here | |
|---|---|---|
| 1 · Cleaning | `import_gutenberg` brings in the most downloaded books per language from the public Gutendex API: it skips books still under copyright, non-text media and books without a summary; cleans titles of leftover catalog codes (`$b`, `::`); flags automatically generated summaries. Running it again updates, never duplicates. | |
| 2 · Context | Each book has a 768-dimension vector (title, author, category, subjects and summary) in Postgres with pgvector and an HNSW index; `embed_books` only redoes the books that changed. For each question: the 12 closest, with summaries, for the summary pass; the 40 closest, title and author only, for the knowledge pass. | |
| 3 · Input guardrail | Each pass asks for JSON with a schema whose `book_id` is an enum of the listed books: naming a book outside the list is structurally impossible. The summary pass also requires a word-for-word `quote`. Questions are capped at 500 characters and to signed-in readers. | ★ |
| 4 · Process | Two calls per question. Summaries: "only with what the summaries say; if a summary does not say why it fits, leave it out". Knowledge: "with what you know about these books; leave out the ones you do not know". | |
| 5 · Output guardrail | `librarian.check_summary_picks` and `check_knowledge_picks` drop: an id not listed, an empty reason, a repeat, more than three, and in the first pass a quote that is not word for word in that book's summary (case, spacing, quote marks and dots aside; at least 20 characters). The page says how many were dropped. What the second pass says is shown as the model's knowledge, unchecked. | ★ |

## Measured

Two sets of questions written for this measurement (not by the model under test), with the books that should come out, by Gutenberg id: [`eval/questions.json`](eval/questions.json) and [`eval/questions_hard.json`](eval/questions_hard.json). `python manage.py evaluate` reproduces the tables and keeps the raw answers in [`eval/results/`](eval/results/). Measured on 28-10-2026 with Gemini's free quota.

**Base set, 36 questions** that describe the plot without the title; Spanish questions for books only in English and the other way round; 2 with no answer in the catalog.

| What | Result |
|---|---|
| Search: the expected book among the first 5 | 34 / 34 (MRR 0.971) |
| Summary pass: recommends it | 32 / 34 |
| Knowledge pass: recommends it | 34 / 34 |
| No answer in the catalog: recommends nothing | 2 / 2 in both passes |
| Quotes that pass the check | 36 / 37 |

**Hard set, 18 questions** of three kinds: *knowledge* (the answer needs a fact no summary has: Lepanto, The Raven, Colliure), *mood* (several right answers, a matter of taste) and *trap* (negations, misleading words, nothing in the catalog).

| Kind | Search: among the first 5 | Summaries | Knowledge | Found only by knowledge | Silent when nothing fits |
|---|---|---|---|---|---|
| Knowledge (7) | 7 / 7 | 7 / 7 | 7 / 7 | 0 | — |
| Mood (5) | 2 / 5 | 3 / 5 | **5 / 5** | **2** | — |
| Trap (6) | 4 / 4 | 4 / 4 | 4 / 4 | 0 | 2 / 2 |

Three things follow from those tables. The base set is easy, and it shows the pipeline works end to end, not how it compares. The second pass earns its place on mood questions: for "a love story with a happy ending" the summaries bring nothing, because none of them tells the ending, and knowledge brings *Pride and Prejudice*, *The Blue Castle* and *The Enchanted April*; "something short I can finish in one sitting" only knowledge solves, because no summary says how long a book is. And search ranks those questions badly (the expected short book came 26th): that is why the knowledge pass looks at 40 books, not 12.

The rejected quote is a real model mistake: it copied *"Edmond Dants"* where the summary says *"Dantès"*. The book was right; the knowledge pass recommended it anyway. The check is not relaxed: a quote is word for word or it does not pass.

## Try it locally

You need Postgres with pgvector: [Neon](https://neon.com)'s free plan works (use the direct connection, not the pooled one). The Gemini key is optional; better from a project without billing, so nothing can be charged.

```bash
python -m venv .venv && .venv/Scripts/activate    # on Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                              # DATABASE_URL and, if you want, GEMINI_API_KEY
python manage.py migrate
python manage.py import_gutenberg                 # 150 books in Spanish and 150 in English
python manage.py embed_books                      # 6 calls of 50 books
python manage.py runserver
python manage.py test                             # 80 tests, never calling Gemini or Gutenberg
python manage.py evaluate --questions eval/questions_hard.json
```

Without `GEMINI_API_KEY` the catalog works the same, by keyword. The librarian then asks each reader for their own key (the "AI key" page): it is kept by their browser, and their browser is what talks to Google.

**Heroku.** `Procfile` with `release: migrate` and gunicorn; WhiteNoise serves static files. Set `DATABASE_URL`, `SECRET_KEY` and, if the site should answer with its own key, `GEMINI_API_KEY` as config vars. On Heroku the site requires HTTPS, secure cookies and HSTS, and does not start without `SECRET_KEY`.

## Limitations

- **A checked quote is not a checked reason.** Code guarantees the quote exists in that book's summary, not that it says what the reason says. A real case: *"Poemas del poeta sevillano que murió en Colliure huyendo de la guerra"* → *Páginas escogidas*, reason *"…Antonio Machado, quien residió en Sevilla y falleció en Colliure"*, quote *"Páginas escogidas by Antonio Machado is a collection of poems"*: Seville and Collioure come from the model, not from the quote. Since the reason has been asked to say only what its quote says, this happens in 2 of the 7 knowledge questions, not in all. Checking it would take another model as judge, and that is no longer code checking.
- The second pass cannot be checked: what the model knows about a book is shown as its own, labelled, and it can be wrong.
- The summaries are generated automatically by Project Gutenberg (285 of 300) and are in English; the site says so on each entry. So quotes come out in English even when the question is in Spanish.
- The sets are small (54 questions) and the mood questions have answers of taste: read them as a smoke test, not a benchmark. On the base set, which does not tell things apart, everything is close to 100%.
- Search "knows" too: "the author of The Raven" puts Poe first though no summary names The Raven, because a book's vector includes its author and the embedding model links one with the other.
- The daily caps live in the process's local cache: enough with one dyno; with several, each would count on its own.
- Some books are in the catalog twice, once per language (*Treasure Island* and *La isla del tesoro*); the librarian may recommend both.

---

## Security and regulation

The same four headings in every repository. **today** rows are what the code does. This repository does not carry the three integration wires (identity, events, sign-off) of [toolkit](https://github.com/epifaneia/toolkit): it is a public demo over public-domain books, with no confidential data to keep.

| | | |
|---|---|---|
| **Confidentiality** | The site's key lives only in `.env` or in the config vars, never in git, and travels to Google in a header, never in the URL. A reader's key lives only in their browser (forgotten when the tab closes unless they ask to keep it) and never reaches the server. What goes to Google is the question and the titles or summaries of the candidate books; the page says so. In the EEA, Switzerland and the UK, Gemini's terms apply the paid-service conditions to the free quota: what is sent is not used to improve their products. | **today** |
| **Traceability** | Every librarian answer is kept in `LibrarianAnswer`: the question, each pass's books, the drops, whether the second pass failed, the model and whose key paid. Not the reader. Read-only in the admin. Measurements keep the model's raw answers. | **today** |
| **Leak prevention** | The model has no credentials and no access to the database: it only sees the list it is given for that question, and can only answer with ids from that list. With a reader's key the server never makes the call: it prepares the list, checks the raw answer with a one-use token tied to that reader, and nothing else. | **today** |
| **Human in the loop** | The librarian recommends; the reader decides. Each recommendation separates what comes from the summary, with its quote, from what comes from the model's knowledge, and the page says how many suggestions were dropped and why. If nothing fits, it says so. | **today** |

Framework: EU AI Act (2024/1689) · GDPR.

---

## Structure

```
library/     models · views · librarian (the two passes and their checks) · search · embeddings · gemini
             gutenberg (import) · evaluation · management/commands/ (import_gutenberg · embed_books · evaluate)
             templates/ · static/library/librarian.js (the reader's key, in the browser only) · tests/ (80 tests)
eval/        questions.json · questions_hard.json · results/ (every measurement, with the raw answers)
django_library/  settings (local and Heroku in one file) · urls
.github/workflows/tests.yml   the tests against Postgres 17 with pgvector on every push
```

Daniel Martín · [epifaneia.dev](https://epifaneia.dev) · Apache-2.0
