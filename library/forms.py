from django import forms

from .models import Review


class SearchForm(forms.Form):
    """Catalog search: one text query over one chosen field."""

    FIELDS = (
        ("title", "Title"),
        ("meaning", "Meaning (AI search)"),
        ("writer", "Writer"),
        ("subjects", "Subject"),
        ("genre", "Category"),
        ("language", "Language"),
        ("isbn", "ISBN"),
    )
    query = forms.CharField(label="Search", max_length=200)
    field = forms.ChoiceField(choices=FIELDS)


class ReviewSearchForm(forms.Form):
    FIELDS = (
        ("title", "Review title"),
        ("book", "Book"),
        ("user", "Reader"),
    )
    query = forms.CharField(label="Search", max_length=200)
    field = forms.ChoiceField(choices=FIELDS)


class UserSearchForm(forms.Form):
    query = forms.CharField(label="Search readers", max_length=150)


class ReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(
        choices=[(i, f"{i} / 5") for i in range(1, 6)],
        coerce=int,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = Review
        fields = ["title", "rating", "content"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "content": forms.Textarea(attrs={"class": "form-control", "rows": 6}),
        }


class CSVImportForm(forms.Form):
    csv_file = forms.FileField(label="CSV file")

    def clean_csv_file(self):
        file = self.cleaned_data["csv_file"]
        if not file.name.lower().endswith(".csv"):
            raise forms.ValidationError("File must be a CSV file.")
        return file
