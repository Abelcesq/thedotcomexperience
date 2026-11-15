from django.urls import path

from . import views

urlpatterns = [
    path("profile/", views.profile, name="profile"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("profile/photo/", views.profile_photo, name="profile_photo"),
    path("photo/<str:member_id>/", views.member_photo, name="member_photo"),
]
