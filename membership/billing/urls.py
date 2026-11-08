from django.urls import path

from . import views

# Mounted under /stripe/
urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("portal/", views.customer_portal, name="customer_portal"),
    path("webhook/", views.webhook, name="stripe_webhook"),
]
