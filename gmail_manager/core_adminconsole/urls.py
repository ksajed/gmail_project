from __future__ import annotations
from django.urls import path
from . import views

app_name = "core_adminconsole"

urlpatterns = [
    path("", views.admin_home, name="home"),
    path("accounts/", views.accounts_list, name="accounts_list"),
    path("accounts/<int:user_id>/toggle-active/", views.account_toggle_active, name="account_toggle_active"),
    path("audit/", views.audit_log, name="audit_log"),
]
