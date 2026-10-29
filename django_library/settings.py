"""Settings for Neuralib.

The same code runs in two places:
- locally: the values in a `.env` file (see `.env.example`);
- on Heroku: config vars set with `heroku config:set`.
Both need DATABASE_URL pointing to Postgres with pgvector (Neon's free plan works).
"""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Heroku sets DYNO and Render sets RENDER: either one means production.
ON_HOST = "DYNO" in os.environ or "RENDER" in os.environ
DEBUG = os.environ.get("DEBUG", "0" if ON_HOST else "1") == "1"

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    if DEBUG or not ON_HOST:
        SECRET_KEY = "dev-only-insecure-key"
    else:
        raise ImproperlyConfigured("SECRET_KEY must be set in production.")

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1,.herokuapp.com,.onrender.com").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    # Before allauth, so library/templates/allauth/ overrides allauth's own layout.
    "library",
    "allauth",
    "allauth.account",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "django_library.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "django_library.wsgi.application"

# Postgres everywhere: semantic search stores its vectors with pgvector.
if not os.environ.get("DATABASE_URL"):
    raise ImproperlyConfigured(
        "Set DATABASE_URL to a Postgres database with pgvector (Neon's free plan works). See .env.example.")
DATABASES = {
    "default": dj_database_url.config(conn_max_age=600, conn_health_checks=True, ssl_require=ON_HOST)
}

# Semantic search: Gemini embeddings. Without a key the catalog still works, by keyword only.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
EMBEDDING_MODEL = "gemini-embedding-001"
# Each search spends one call of the free quota; these caps keep the demo inside it.
SEMANTIC_SEARCHES_PER_VISITOR_PER_DAY = int(os.environ.get("SEMANTIC_SEARCHES_PER_VISITOR_PER_DAY", "30"))
SEMANTIC_SEARCHES_PER_DAY = int(os.environ.get("SEMANTIC_SEARCHES_PER_DAY", "500"))
# The librarian. With GEMINI_API_KEY set it answers with the site's key, within these caps;
# without it, each reader brings their own key, which stays in their browser.
LIBRARIAN_MODEL = "gemini-3.5-flash-lite"
LIBRARIAN_QUESTIONS_PER_READER_PER_DAY = int(os.environ.get("LIBRARIAN_QUESTIONS_PER_READER_PER_DAY", "10"))
LIBRARIAN_QUESTIONS_PER_DAY = int(os.environ.get("LIBRARIAN_QUESTIONS_PER_DAY", "200"))

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# Accounts: username and password; no email confirmation (no mail server in this demo).
ACCOUNT_LOGIN_METHODS = {"username"}
ACCOUNT_SIGNUP_FIELDS = ["username*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
LOGIN_REDIRECT_URL = "/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Europe/Madrid"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if ON_HOST
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

if ON_HOST:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Short on purpose: raise it once the site has run on HTTPS for a while.
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "3600"))
    # Subdomains and the preload list are the domain owner's call, not the app's.
    SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]
