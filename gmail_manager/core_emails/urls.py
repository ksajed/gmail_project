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
    path("dashboard/renewals/", views.renewals_dashboard, name="renewals_dashboard"),

    # 🔄 SYNC GMAIL
    path(
        "dashboard/sync-gmail/",
        views.sync_gmail_now,
        name="sync_gmail_now",
    ),

    # 📄 ORDONNANCE — DÉTAIL
    path(
        "prescription/<int:pk>/",
        views.prescription_detail,
        name="prescription_detail",
    ),

    # 🔁 CHANGEMENT DE STATUT
    path(
        "prescription/<int:pk>/change-status/",
        views.change_status,
        name="change_status",
    ),

    # 🧾 TYPE D’ORDONNANCE (V3 — ORGANISATIONNEL)
    path(
        "prescription/<int:pk>/change-prescription-type/",
        views.change_prescription_type,
        name="change_prescription_type",
    ),

    # 🧑‍⚕️ ORIGINE / EXPÉDITEUR
    path(
        "prescription/<int:pk>/change-sender-type/",
        views.change_sender_type,
        name="change_sender_type",
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

    # ➕ CRÉATION ORDONNANCE MANUELLE
    path(
        "prescription/new/",
        views.prescription_create,
        name="prescription_create",
    ),

    # =====================================================
    # V7 — RENOUVELLEMENT (ACTIONS)
    # =====================================================
    
    path(
    "renewal/<int:pk>/update/",
    views.update_renewal_info,
    name="update_renewal_info",
        ),

          path(
          "renewal/<int:pk>/done/",
          views.mark_renewal_done,
          name="mark_renewal_done",
      ),

    
    path(
        "renewal/<int:pk>/patient-email/<int:days>/",
        views.send_renewal_patient_email,
        name="send_renewal_patient_email",
    ),
    path(
        "renewal/<int:pk>/patient-sms/<int:days>/",
        views.send_renewal_patient_sms,
        name="send_renewal_patient_sms",
    ),
    path(
        "renewal/<int:pk>/doctor-email/",
        views.send_renewal_doctor_email,
        name="send_renewal_doctor_email",
    ),

    # 🔔 NOTIFICATIONS — PARAMÉTRAGE PAR ORDONNANCE (V8)
    path(
        "prescription/<int:prescription_id>/notifications/",
        views.update_prescription_notification_settings,
        name="update_prescription_notification_settings",
    ),

]
