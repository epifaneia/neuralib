from django import forms
from .models import Book, Review


class BaseSearchForm(forms.Form):
    query = forms.CharField(label='Search:', required=True)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['field'] = forms.ChoiceField(choices=self.SEARCH_FIELDS)

class SearchForm(BaseSearchForm):
    SEARCH_FIELDS = (
        ('title', 'Title'),
        ('writer', 'Writer'),
        ('genre', 'Genre'),
        ('editorial', 'Editorial'),
        ('isbn', 'ISBN'),
    )
    field = forms.ChoiceField(choices=SEARCH_FIELDS)

class UserSearchForm(BaseSearchForm):
    SEARCH_FIELDS = (
        ('username', 'User Name'),
        ('reviews', 'Reviews'),
        ('ratings', 'Ratings'),
    )
    field = forms.ChoiceField(choices=SEARCH_FIELDS)

class ReviewForm(BaseSearchForm):
    SEARCH_FIELDS = (
        ('username', 'User Name'),
        ('title', 'Title'),
        ('book'), 'Book'
    )
    field = forms.ChoiceField(choices=SEARCH_FIELDS)



class CSVImportForm(forms.Form):
    csv_file = forms.FileField()

    def clean_csv_file(self):
        file = self.cleaned_data.get('csv_file')
        if file:
            if not file.name.endswith('.csv'):
                raise forms.ValidationError("File must be a CSV file.")
        return file

class SelectBookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ['title']

