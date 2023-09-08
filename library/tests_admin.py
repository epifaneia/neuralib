from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
import os
import tempfile


class BookAdminTestCase(TestCase):
    fixtures = ['initial_data.json']  # Ensure this file actually exists

    def setUp(self):
        super().setUp()
        # Login logic here, if needed

    def test_import_csv_non_utf8_file(self):
        url = reverse('admin:import_csv')

        # Creating a non-UTF8 encoded file using tempfile
        with tempfile.NamedTemporaryFile(delete=False, mode='wb') as temp_file:
            temp_file.write('name,author\n'.encode('utf-8'))
            temp_file.write('Название,Автор\n'.encode('windows-1251'))

        with open(temp_file.name, 'rb') as file:
            response = self.client.post(url, {'file': file}, follow=True)

        # Cleanup
        os.remove(temp_file.name)

        # Check if the response contains a specific message and status code
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'The file is not in UTF-8 format')
