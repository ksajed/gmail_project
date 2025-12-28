# gmail_manager/gmail_manager/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),

    # Apps existantes
    path("", include("core_attachments.urls")),
    path("", include("core_emails.urls")),

    # ✅ AJOUT — patients (compléter patient)
    path("", include("core_patients.urls")),
]
