from django.core.management.base import BaseCommand

from library.models import Book

NOGUM = {
    "description": (
        "NOGUM es un juego de rol universal escrito por el autor de esta biblioteca: un manual de unas 150 "
        "páginas en castellano y en inglés, una versión acelerada de 16 páginas para empezar a jugar enseguida "
        "y una aplicación que prepara la partida con preguntas sobre situaciones, no sobre reglas. No es de "
        "dominio público: lo publica su autor."
    ),
    "genre": "Games",
    "subjects": "Role-playing games; Game design",
    "language": "es",
    "read_online": "https://epifaneia.dev/nogum/",
}


class Command(BaseCommand):
    help = "Add the one book in the catalog that is not from Project Gutenberg. Safe to run again."

    def handle(self, *args, **options):
        _, created = Book.objects.update_or_create(title="NOGUM", writer="Daniel Martín", defaults=NOGUM)
        self.stdout.write("NOGUM added." if created else "NOGUM updated.")
