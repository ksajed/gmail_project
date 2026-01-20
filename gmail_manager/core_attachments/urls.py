# gmail_manager/core_attachments/urls.py
from django.urls import path
from . import views

app_name = "core_attachments"

urlpatterns = [
    path(
        "<int:attachment_id>/view/",
        views.view_attachment,
        name="view_attachment",
    ),
    path(
        "<int:attachment_id>/download/",
        views.download_attachment,
        name="download_attachment",
    ),
    path(
        "<int:attachment_id>/viewer/",
        views.attachment_viewer,
        name="attachment_viewer",
    ),
]
