from django.urls import path
from django.views.generic import RedirectView
from . import views
from .views import PharmacyLoginView, PharmacyLogoutView

app_name = "core_emails"

urlpatterns = [
    # 🔁 RACINE → DASHBOARD
    path("", RedirectView.as_view(url="/dashboard/", permanent=False)),

    # 🔐 AUTH
    path("login/", PharmacyLoginView.as_view(), name="login"),
    path("logout/", PharmacyLogoutView.as_view(), name="logout"),

    # 🏠 DASHBOARD
    path("dashboard/", views.dashboard, name="dashboard"),

    # 🔄 SYNC GMAIL
    path(
        "dashboard/sync-gmail/",
        views.sync_gmail_now,
        name="sync_gmail_now",
    ),

    # 📄 ORDONNANCES
    path(
        "prescription/<int:pk>/",
        views.prescription_detail,
        name="prescription_detail",
    ),

    path(
        "prescription/<int:pk>/change-status/",
        views.change_status,
        name="change_status",
    ),
]
