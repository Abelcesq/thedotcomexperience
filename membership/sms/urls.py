from django.urls import path

from . import views

urlpatterns = [path("inbound/", views.inbound, name="sms_inbound")]
