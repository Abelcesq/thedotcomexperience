from django.contrib import admin
from django.urls import path, include

from dots import views as dots_views

urlpatterns = [
    path("admin/", admin.site.urls),
    # Public pages
    path("", dots_views.home, name="home"),
    path("join/", include("billing.urls_join")),
    path("dots/", include("dots.urls")),
    # Auth (allauth) + our profile pages under /accounts/
    path("accounts/", include("accounts.urls")),       # profile, edit (our views)
    path("accounts/", include("allauth.urls")),        # login, signup, password, etc.
    # Stripe
    path("stripe/", include("billing.urls")),
]
