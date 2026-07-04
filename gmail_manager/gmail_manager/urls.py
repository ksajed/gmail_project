# gmail_manager/gmail_manager/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("anomalies/", include("core_anomalies.urls")),
    path('admin-console/', include('core_adminconsole.urls')),
    path("admin/", admin.site.urls),

    # Apps existantes
    path("", include("core_attachments.urls")),
    path("", include("core_emails.urls")),

    # ✅ AJOUT — patients (compléter patient)
    path("", include("core_patients.urls")),
]
