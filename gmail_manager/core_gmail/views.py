# gmail_manager/core_emails/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from core_emails.models import Prescription
from core_gmail.services import fetch_new_gmail_messages

from django.contrib.auth.views import LoginView, LogoutView


@login_required
def pharmacy_dashboard(request):
    """
    Dashboard principal de la pharmacie.
    """

    prescriptions = (
        Prescription.objects
        .select_related("patient")
        .prefetch_related("attachments", "status_history")
        .order_by("-received_at")
    )
    return render(
        request,
        "core_emails/dashboard.html",
        {
            "prescriptions": prescriptions
        }
    )


@login_required
def sync_gmail_now(request):
    """
    Synchronisation Gmail manuelle via bouton.
    """
    fetch_new_gmail_messages()
    return redirect("pharmacy_dashboard")



#✅ AJOUT — VUES D’AUTHENTIFICATION PERSONNALISÉES

class PharmacyLoginView(LoginView):
    template_name = "auth/login.html"


class PharmacyLogoutView(LogoutView):
    pass


