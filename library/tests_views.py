from django.test import TestCase
from django.urls import reverse
from library.models import Book


class LibraryHomeViewTest(TestCase):
    def test_library_home_view_status_code(self):
        url = reverse('library_home')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_library_home_view_template(self):
        url = reverse('library_home')
        response = self.client.get(url)
        self.assertTemplateUsed(response, 'library/library_home.html')


class CatalogViewTest(TestCase):

    def setUp(self):
        self.books = []
        for i in range(1, 7):
            book = Book.objects.create(
                title=f'Book{i}',
                description=f'Description{i}',
                genre=f'genre{i}',
                num_pages=300 + i * 10,
                editorial=f'Editorial{i}',
                isbn=f'12345678901{i:02}',
                year_edition=2020 + i,
                date_edition=f'{2020 + i}-01-01',
                writer=f'Writer{i}'
            )
        self.books.append(book)

    def test_catalog_view_status_code(self):
        url = reverse('catalog')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_catalog_view_template(self):
        url = reverse('catalog')
        response = self.client.get(url)
        self.assertTemplateUsed(response, 'library/catalog.html')

    def test_catalog_search_by_title(self):
        url = reverse('catalog')
        response = self.client.get(url, {'query': 'Book1', 'field': 'title'})
        self.assertIn(self.book1, response.context['books'])

    def test_catalog_search_by_writer(self):
        url = reverse('catalog')
        response = self.client.get(
            url, {'query': 'Writer1', 'field': 'writer'})
        self.assertIn(self.book1, response.context['books'])

    def test_catalog_search_by_genre(self):
        url = reverse('catalog')
        response = self.client.get(
            url, {'query': 'fantasy_magic', 'field': 'genre'})
        self.assertIn(self.book1, response.context['books'])

    def test_catalog_search_by_editorial(self):
        url = reverse('catalog')
        response = self.client.get(
            url, {'query': 'Editorial1', 'field': 'editorial'})
        self.assertIn(self.book1, response.context['books'])

    def test_catalog_search_by_isbn(self):
        url = reverse('catalog')
        response = self.client.get(
            url, {'query': '1234567890123', 'field': 'isbn'})
        self.assertIn(self.book1, response.context['books'])

    def test_catalog_search_no_results(self):
        url = reverse('catalog')
        response = self.client.get(
            url, {'query': 'NonExistent', 'field': 'title'})
        self.assertNotIn(self.book1, response.context['books'])

    def test_catalog_search_invalid_field(self):
        url = reverse('catalog')
        response = self.client.get(
            url, {'query': 'Book1', 'field': 'invalid_field'})
        self.assertEqual(response.status_code, 200)

    def test_catalog_pagination_paginator(self):
        url = reverse('catalog')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context['books'].paginator, Paginator)

    def test_catalog_pagination_page_obj(self):
        url = reverse('catalog')
        response = self.client.get(url + '?page=2')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(hasattr(response.context['books'], 'number'))
        current_page = response.context['books'].number
        self.assertEqual(current_page, 2)

    def test_catalog_pagination_page_number(self):
        url = reverse('catalog')
        response = self.client.get(url + '?page=2')
        self.assertEqual(response.status_code, 200)
        page_number = response.wsgi_request.GET.get('page')
        self.assertEqual(page_number, '2')

    def test_catalog_pagination(self):
        url = reverse('catalog')
        response = self.client.get(url + '?page=2')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Page 2")


class EventsViewTest(TestCase):
    def test_events_view_status_code(self):
        url = reverse('events')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_events_view_template(self):
        url = reverse('events')
        response = self.client.get(url)
        self.assertTemplateUsed(response, 'library/events.html')

    def test_events_view_content(self):
        url = reverse('events')
        response = self.client.get(url)
        self.assertContains(response, "Expected Content for Events")


class ContactViewTest(TestCase):
    def test_contact_view_status_code(self):
        url = reverse('contact')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_contact_view_template(self):
        url = reverse('contact')
        response = self.client.get(url)
        self.assertTemplateUsed(response, 'library/contact.html')

    def test_contact_view_content(self):
        url = reverse('contact')
        response = self.client.get(url)
        self.assertContains(response, "Expected Content for Contact")


class AboutViewTest(TestCase):
    def test_about_view_status_code(self):
        url = reverse('about')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_about_view_template(self):
        url = reverse('about')
        response = self.client.get(url)
        self.assertTemplateUsed(response, 'library/about.html')
