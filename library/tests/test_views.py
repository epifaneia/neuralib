from django.test import TestCase
from django.urls import reverse

from library.models import Review

from .factories import make_book, make_review, make_user


class PublicPagesTests(TestCase):
    def setUp(self):
        self.hobbit = make_book()
        self.dune = make_book(title="Dune", writer="Frank Herbert", genre="science_fiction_new", isbn="9780441013593")

    def test_pages_load(self):
        for name in ("library_home", "catalog", "reviews", "users", "account_login", "account_signup"):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_catalog_search_by_writer(self):
        response = self.client.get(reverse("catalog"), {"query": "herbert", "field": "writer"})
        self.assertEqual([b.title for b in response.context["books"]], ["Dune"])

    def test_catalog_search_by_isbn(self):
        response = self.client.get(reverse("catalog"), {"query": "9780441", "field": "isbn"})
        self.assertEqual([b.title for b in response.context["books"]], ["Dune"])

    def test_invalid_search_field_returns_everything(self):
        response = self.client.get(reverse("catalog"), {"query": "x", "field": "password"})
        self.assertEqual(len(response.context["books"]), 2)

    def test_catalog_paginates_and_keeps_the_search(self):
        for i in range(6):
            make_book(title=f"Hobbit fan fiction {i}")
        response = self.client.get(reverse("catalog"), {"query": "hobbit", "field": "title", "page": 2})
        self.assertEqual(response.context["books"].number, 2)
        self.assertContains(response, "query=hobbit&amp;field=title&amp;page=1")

    def test_reviews_search_by_reader(self):
        make_review(make_user("ana"), self.hobbit)
        make_review(make_user("luis"), self.dune)
        response = self.client.get(reverse("reviews"), {"query": "ana", "field": "user"})
        self.assertEqual([r.user.username for r in response.context["reviews"]], ["ana"])

    def test_readers_show_review_count(self):
        ana = make_user("ana")
        make_review(ana, self.hobbit)
        make_review(ana, self.dune)
        response = self.client.get(reverse("users"))
        self.assertContains(response, "2 reviews")

    def test_home_shows_latest_reviews(self):
        make_review(make_user("ana"), self.hobbit, title="Second breakfast")
        self.assertContains(self.client.get(reverse("library_home")), "Second breakfast")


class ReviewWritingTests(TestCase):
    def setUp(self):
        self.book = make_book()
        self.user = make_user()
        self.url = reverse("review_book", args=[self.book.id])

    def test_login_required(self):
        for url in (reverse("add_review"), self.url):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, f"{reverse('account_login')}?next={url}")

    def test_write_a_review(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {"title": "Great", "rating": "5", "content": "Loved it."})
        self.assertRedirects(response, reverse("reviews"))
        review = Review.objects.get()
        self.assertEqual((review.user, review.book, review.rating), (self.user, self.book, 5))

    def test_second_review_edits_the_first(self):
        make_review(self.user, self.book, title="First take")
        self.client.force_login(self.user)
        self.assertTrue(self.client.get(self.url).context["editing"])
        self.client.post(self.url, {"title": "Second take", "rating": "3", "content": "Changed my mind."})
        self.assertEqual(Review.objects.get().title, "Second take")

    def test_invalid_review_shows_errors(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {"title": "", "rating": "5", "content": "x"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Review.objects.exists())

    def test_missing_book_is_404(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("review_book", args=[999])).status_code, 404)


class AccountTests(TestCase):
    def test_account_pages_use_the_site_layout(self):
        for name in ("account_login", "account_signup"):
            with self.subTest(page=name):
                self.assertTemplateUsed(self.client.get(reverse(name)), "library/base.html")

    def test_login_page_has_no_dead_reset_link(self):
        response = self.client.get(reverse("account_login"))
        self.assertNotContains(response, "Forgot your password?")
        self.assertContains(response, "Ask the site administrator")

    def test_sign_up_with_username_only(self):
        response = self.client.post(reverse("account_signup"), {
            "username": "newreader",
            "password1": "a-long-test-password",
            "password2": "a-long-test-password",
        })
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertTrue(response.wsgi_request.user.is_authenticated)
