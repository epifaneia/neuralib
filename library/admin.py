import csv

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import path

from .forms import CSVImportForm
from .models import Book, LibrarianAnswer, Review

# CSV columns, in order. ISBN is optional (older files have 10 columns).
CSV_COLUMNS = ["title", "description", "genre", "num_pages", "editorial", "year_edition",
               "writer", "image_url", "read_online", "download_link", "isbn"]


def import_books(text):
    """Create books from CSV text (header row first). Returns (created, errors)."""
    rows = csv.reader(text.splitlines())
    next(rows, None)
    created, errors = 0, []
    for line, row in enumerate(rows, start=2):
        if len(row) not in (len(CSV_COLUMNS) - 1, len(CSV_COLUMNS)):
            errors.append(f"Line {line}: expected {len(CSV_COLUMNS) - 1} or {len(CSV_COLUMNS)} columns, got {len(row)}.")
            continue
        data = dict(zip(CSV_COLUMNS, (cell.strip() for cell in row)))
        for optional in ("image_url", "read_online", "download_link", "num_pages", "year_edition"):
            data[optional] = data[optional] or None
        try:
            book = Book(**data)
            book.full_clean()
        except (ValidationError, ValueError) as error:
            errors.append(f"Line {line}: {error}")
            continue
        book.save()
        created += 1
    return created, errors


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    change_list_template = "admin/book_changelist.html"
    list_display = ("title", "writer", "language", "genre", "gutenberg_id")
    list_filter = ("language", "summary_is_generated")
    search_fields = ("title", "writer", "editorial", "isbn", "subjects")

    def get_urls(self):
        custom = [path("import-csv/", self.admin_site.admin_view(self.import_csv), name="library_book_import_csv")]
        return custom + super().get_urls()

    def import_csv(self, request):
        form = CSVImportForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            try:
                text = form.cleaned_data["csv_file"].read().decode("utf-8")
            except UnicodeDecodeError:
                messages.error(request, "The file is not in UTF-8 format.")
                return redirect("admin:library_book_changelist")
            created, errors = import_books(text)
            for error in errors:
                messages.error(request, error)
            messages.success(request, f"{created} book(s) imported.")
            return redirect("admin:library_book_changelist")
        context = {**self.admin_site.each_context(request), "form": form, "title": "Import books from CSV"}
        return render(request, "admin/csv_form.html", context)


@admin.register(LibrarianAnswer)
class LibrarianAnswerAdmin(admin.ModelAdmin):
    """The log of the librarian's answers: read-only, it is a record."""

    list_display = ("created", "question", "picks", "dropped", "knowledge_picks", "knowledge_dropped", "key", "model")
    list_filter = ("key", "model", "knowledge_failed")
    search_fields = ("question",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("__str__", "rating", "timestamp")
    list_filter = ("rating", "timestamp")
    search_fields = ("user__username", "book__title", "title", "content")
    readonly_fields = ("timestamp",)
