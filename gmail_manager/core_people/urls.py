from django.urls import path
from . import views

app_name = "core_people"

urlpatterns = [
    path(
        "nurses/create/",
        views.create_nurse,
        name="create_nurse",
    ),
]
