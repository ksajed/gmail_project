from __future__ import annotations
from django.urls import path
from . import views

app_name = "core_adminconsole"

urlpatterns = [
    # Home
    path("", views.admin_home, name="home"),

    # Patients
    path("patients/", views.patients_list, name="patients_list"),
    path("patients/<int:pk>/edit/", views.patient_edit, name="patient_edit"),

    # Users / Accounts / Groups / IAM
    path("users/", views.users_home, name="users_home"),
    path("accounts/", views.accounts_list, name="accounts_list"),
    path("accounts/create/", views.account_create, name="account_create"),
    path("accounts/<int:user_id>/edit/", views.account_edit, name="account_edit"),
    path("accounts/<int:user_id>/toggle-active/", views.account_toggle_active, name="account_toggle_active"),
    path("accounts/<int:user_id>/soft-delete/", views.account_soft_delete_confirm, name="account_soft_delete_confirm"),
    path("accounts/<int:user_id>/soft-delete/do/", views.account_soft_delete, name="account_soft_delete"),
    path("accounts/<int:user_id>/reactivate/", views.account_reactivate, name="account_reactivate"),

    path("groups/", views.groups_list, name="groups_list"),
    path("groups/create/", views.group_create, name="group_create"),
    path("groups/<int:group_id>/edit/", views.group_edit, name="group_edit"),
    path("groups/<int:group_id>/delete/", views.group_delete_confirm, name="group_delete_confirm"),
    path("groups/<int:group_id>/delete/do/", views.group_delete, name="group_delete"),

    path("iam/", views.iam_matrix, name="iam_matrix"),

    # Nurses
    path("nurses/", views.nurses_list, name="nurses_list"),
    path("nurses/create/", views.nurse_create, name="nurse_create"),
    path("nurses/<int:pk>/edit/", views.nurse_edit, name="nurse_edit"),
    path("nurses/<int:pk>/<str:action>/", views.nurse_toggle_confirm, name="nurse_toggle_confirm"),

    # Prescriptions (Admin Console)
    path("prescriptions/", views.prescriptions_search, name="prescriptions_list"),
    path("prescriptions/", views.prescriptions_search, name="prescriptions_search"),
    path("prescriptions/trash/", views.prescriptions_trash, name="prescriptions_trash"),
    path("prescriptions/bulk-action/", views.prescriptions_bulk_action, name="prescriptions_bulk_action"),
    path("prescriptions/<int:pk>/trash/", views.prescription_soft_delete, name="prescription_soft_delete"),
    path("prescriptions/<int:pk>/restore/", views.prescription_restore, name="prescription_restore"),
    path("prescriptions/<int:pk>/purge/", views.prescription_purge, name="prescription_purge"),

    # Notifications / Gmail tools
    path("notifications/", views.notifications_settings, name="notifications_settings"),
    path("gmail/", views.gmail_tools, name="gmail_tools"),

    # Audit
    path("audit/", views.audit_log, name="audit_log"),
    path("audit/export/", views.audit_export_csv, name="audit_export_csv"),
    path("audit/clear/", views.audit_clear, name="audit_clear"),
]
