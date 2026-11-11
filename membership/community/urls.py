from django.urls import path

from . import views

urlpatterns = [
    path("", views.directory, name="member_directory"),
    path("connections/", views.connections, name="connections"),
    path("messages/", views.inbox, name="member_inbox"),
    path("messages/<str:member_id>/", views.thread, name="member_thread"),
    path("team/", views.my_team, name="my_team"),
    path("<str:member_id>/", views.member_profile, name="member_profile"),
    path("<str:member_id>/connect/", views.connect, name="member_connect"),
    path("<str:member_id>/accept/", views.respond, {"action": "accept"}, name="member_accept"),
    path("<str:member_id>/decline/", views.respond, {"action": "decline"}, name="member_decline"),
    path("<str:member_id>/disconnect/", views.disconnect, name="member_disconnect"),
    path("<str:member_id>/block/", views.block, name="member_block"),
    path("<str:member_id>/unblock/", views.unblock, name="member_unblock"),
    path("<str:member_id>/report/", views.report, name="member_report"),
]
