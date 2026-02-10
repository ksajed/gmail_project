from django.contrib import messages
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from .models import Person
from core_notifications.utils_phone import to_e164_fr


@login_required
@require_POST
def create_nurse(request):
    """
    Création rapide d'un infirmier (organisationnel).
    Email + Téléphone FR obligatoires.
    """
    first_name = (request.POST.get("first_name") or "").strip()
    last_name = (request.POST.get("last_name") or "").strip()
    email = (request.POST.get("email") or "").strip().lower()
    phone_raw = (request.POST.get("phone_number") or "").strip()
    phone_e164 = to_e164_fr(phone_raw)

    if not first_name or not last_name or not email or not phone_e164:
        messages.error(request, "Nom, prénom, email et téléphone (France) sont obligatoires.")
        return redirect(request.META.get("HTTP_REFERER", "/"))

