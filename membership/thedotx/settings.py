"""
Django settings for The Dot Com Experience membership platform.

Secrets come from environment variables (never commit them). See .env.example.
Dev uses SQLite automatically; set DATABASE_URL (Heroku provides it) for Postgres.
"""
from pathlib import Path
import os

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")  # load local .env if present (dev only)


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


# --- Core -----------------------------------------------------------------
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = env_bool("DJANGO_DEBUG", False)

ALLOWED_HOSTS = [h.strip() for h in os.environ.get(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,.herokuapp.com,members.thedotx.com"
).split(",") if h.strip()]

CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.environ.get(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "https://www.thedotx.com,https://thedotx.com,"
    "https://www.thedotcomexperience.com,https://thedotcomexperience.com,"
    "https://members.thedotx.com,"
    "https://*.herokuapp.com",  # lets a test Heroku deploy's admin/forms work out of the box
).split(",") if o.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # Auth (allauth)
    "allauth",
    "allauth.account",
    # Our apps
    "accounts",
    "dots",
    "billing",
    "community",
    "sms",
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

ROOT_URLCONF = "thedotx.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "billing.context_processors.membership_flags",
                "community.context_processors.community_counts",
            ],
        },
    },
]

WSGI_APPLICATION = "thedotx.wsgi.application"

# --- Database -------------------------------------------------------------
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        ssl_require=env_bool("DATABASE_SSL", False),
    )
}

# --- Auth / allauth -------------------------------------------------------
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

SITE_ID = 1

# allauth: email-based login, verification on in prod
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = os.environ.get("ACCOUNT_EMAIL_VERIFICATION", "optional")
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_FORMS = {"signup": "accounts.forms.DotxSignupForm"}
ACCOUNT_ADAPTER = "accounts.adapter.DotxAccountAdapter"

LOGIN_REDIRECT_URL = "/accounts/profile/"
LOGOUT_REDIRECT_URL = "/"
LOGIN_URL = "/accounts/login/"

# Email: console in dev; set EMAIL_* / RESEND for prod (or reuse the Node funnel).
if env_bool("USE_SMTP", False):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = True
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "The Dot Com Experience <info@thedotcomexperience.com>")

# --- Organization (tiers) -------------------------------------------------
# Size limits from the Charter schedules. Going over shows a warning in the admin;
# it does not block the save (the Charters allow short, approved exceptions).
TIER_CAPS = {
    "members_per_ambassador": int(os.environ.get("CAP_MEMBERS_PER_AMBASSADOR", "30")),
    "ambassadors_per_local_leader": int(os.environ.get("CAP_AMBASSADORS_PER_LOCAL_LEADER", "10")),
    "local_leaders_per_regional": int(os.environ.get("CAP_LOCAL_LEADERS_PER_REGIONAL", "10")),
}

# --- Community (directory, connections, messages) -------------------------
COMMUNITY_MAX_REQUESTS_PER_DAY = int(os.environ.get("COMMUNITY_MAX_REQUESTS_PER_DAY", "20"))
COMMUNITY_MAX_MESSAGES_PER_5_MIN = int(os.environ.get("COMMUNITY_MAX_MESSAGES_PER_5_MIN", "30"))
COMMUNITY_MESSAGE_MAX_LENGTH = 2000

# --- Text messages (Twilio) -----------------------------------------------
# Leave these unset and no texts are ever sent. Set the account SID, the auth token,
# and either a Messaging Service SID (preferred) or a sending number to switch texting on.
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_MESSAGING_SERVICE_SID = os.environ.get("TWILIO_MESSAGING_SERVICE_SID", "")
TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "")
SMS_BRAND = os.environ.get("SMS_BRAND", "The Dot Com Experience")
SMS_REMINDER_HOURS_BEFORE = float(os.environ.get("SMS_REMINDER_HOURS_BEFORE", "3"))
SMS_QUIET_START_HOUR = 8     # never text before 8am ...
SMS_QUIET_END_HOUR = 21      # ... or after 9pm, in the Dot's time zone

# --- Stripe ---------------------------------------------------------------
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "")          # the $100/mo recurring Price
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_ALLOW_PROMOTION_CODES = env_bool("STRIPE_ALLOW_PROMOTION_CODES", True)
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000")   # for Stripe return URLs
MEMBERSHIP_PRICE_LABEL = os.environ.get("MEMBERSHIP_PRICE_LABEL", "$100 / month")

# --- i18n / tz ------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

# --- Static ---------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Security (production) ------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "2592000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
