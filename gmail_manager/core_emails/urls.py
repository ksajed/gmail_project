# gmail_manager/core_emails/urls.py
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

    # 🅰️ AFFECTATION INFIRMIER (V2)
    path(
        "prescription/<int:pk>/assign-nurse/",
        views.assign_nurse,
        name="assign_nurse",
    ),
    path(
    "prescription/<int:pk>/unassign-nurse/",
    views.unassign_nurse,
    name="unassign_nurse",  
    ),
    path(
    "nurse/create/",
    views.create_nurse,
    name="create_nurse",    
    ),

    path(
    "prescription/<int:pk>/change-type/",
    views.change_sender_type,
    name="change_sender_type",
    ),
    
    path(
    "prescription/new/",
    views.prescription_create,
    name="prescription_create",
        ),


]
