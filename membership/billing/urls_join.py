from django.urls import path

from . import views

# Mounted at /join/
urlpatterns = [
    path("", views.join, name="join"),
]
