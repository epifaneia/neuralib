from django.core.management.base import BaseCommand

from library.gutenberg import popular_books
from library.models import Book


class Command(BaseCommand):
    help = "Import the most downloaded Project Gutenberg books for each language. Safe to run again: books are matched by Gutenberg id."

    def add_arguments(self, parser):
        parser.add_argument("--language", action="append", dest="languages",
                            help="ISO code, repeatable (default: es and en).")
        parser.add_argument("--count", type=int, default=150, help="Books per language (default: 150).")

    def handle(self, *args, languages=None, count=150, **options):
        for language in languages or ["es", "en"]:
            created = updated = 0
            for gutenberg_id, fields in popular_books(language, count):
                _, new = Book.objects.update_or_create(gutenberg_id=gutenberg_id, defaults=fields)
                created += new
                updated += not new
            self.stdout.write(f"{language}: {created} created, {updated} updated.")
