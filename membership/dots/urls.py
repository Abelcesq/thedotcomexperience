from django.urls import path

from . import views

urlpatterns = [
    path("", views.dots_finder, name="dots_finder"),
    path("data.json", views.dots_data, name="dots_data"),
    path("waitlist/", views.waitlist_signup, name="waitlist_signup"),
    path("request/", views.request_dot, name="request_dot"),
]
