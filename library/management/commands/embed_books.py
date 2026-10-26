from django.core.management.base import BaseCommand, CommandError

from library.embeddings import BATCH, book_text, embed, text_hash
from library.gemini import GeminiError, QuotaExceeded
from library.models import Book


class Command(BaseCommand):
    help = "Compute the search vector of every book that has none or whose text changed since. Safe to run again."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Only say how many books would be embedded.")

    def handle(self, *args, dry_run=False, **options):
        pending = []
        for book in Book.objects.all():
            text = book_text(book)
            if book.embedding is None or book.embedding_hash != text_hash(text):
                pending.append((book, text))
        self.stdout.write(f"{len(pending)} book(s) to embed.")
        if dry_run:
            return
        done = 0
        # Saved batch by batch: if the free quota runs out halfway, the work done so far is kept.
        for start in range(0, len(pending), BATCH):
            chunk = pending[start:start + BATCH]
            try:
                vectors = embed([text for _, text in chunk], "RETRIEVAL_DOCUMENT")
            except QuotaExceeded as error:
                raise CommandError(f"{done} book(s) embedded before the quota ran out; run this again later.") from error
            except GeminiError as error:
                raise CommandError(str(error)) from error
            for (book, text), vector in zip(chunk, vectors):
                book.embedding, book.embedding_hash = vector, text_hash(text)
            Book.objects.bulk_update([book for book, _ in chunk], ["embedding", "embedding_hash"])
            done += len(chunk)
        self.stdout.write(f"{done} book(s) embedded.")
