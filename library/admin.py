from .forms import CSVImportForm
from .models import Book, Review
from django.shortcuts import render, redirect
from django.urls import path
from django.contrib import admin
import csv
import sys
from datetime import datetime
from django.contrib import messages
from django import forms


print("Python Paths:", sys.path)


class ReviewAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'timestamp')  # Display review summary and timestamp
    list_filter = ('user__username', 'book__title', 'timestamp')  # Filters by username, book title, and timestamp
    search_fields = ('user__username', 'book__title', 'content')  # Searchable by username, book title, and content
    readonly_fields = ('timestamp',)  # Making timestamp read-only as it's auto-generated
    
    # If you want to use custom forms
    # form = YourCustomReviewForm
    
    def __str__(self):
        return f"Review Admin"


# Register it with the model
admin.site.register(Review, ReviewAdmin)


class BookAdmin(admin.ModelAdmin):
    change_list_template = 'admin/book_changelist.html'

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('import-csv/', self.import_csv),
        ]
        return my_urls + urls



    def import_csv(self, request):
        if request.method == "POST":
            csv_file = request.FILES["csv_file"]

            # Attempt to decode the file as UTF-8
            try:
                file_content = csv_file.read().decode('utf-8')
            except UnicodeDecodeError:
                messages.error(request, "The file is not in UTF-8 format")
                return redirect("..")

            reader = csv.reader(file_content.splitlines())
            next(reader)  # Skip the header row

            expected_columns = 10  # Expected number of columns

            for row in reader:
                if len(row) != expected_columns:
                    messages.error(
                        request, f"Row with incorrect number of columns: {row}")
                    continue  # Skip this row and continue with the next one

                try:

                    book = Book(
                        title=row[0],
                        description=row[1],
                        genre=row[2],
                        num_pages=int(row[3]),
                        editorial=row[4],
                        year_edition=int(row[5]),
                        writer=row[6],
                        image_url=row[7],
                        read_online=row[8],
                        download_link=row[9]

                    )
                    book.save()
                except ValueError as e:
                    messages.error(
                        request, f"Error processing the row {row}: {e}")
                    continue  # Skip this row and continue with the next one

            messages.success(request, "CSV file has been imported")
            return redirect("..")

        form = CSVImportForm()
        payload = {"form": form}
        return render(request, "admin/csv_form.html", payload)


admin.site.register(Book, BookAdmin)
