from django.contrib import messages
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from .models import Person


@login_required
@require_POST
def create_nurse(request):
    """
    Création rapide d'un infirmier (organisationnel).
    """
    first_name = request.POST.get("first_name")
    last_name = request.POST.get("last_name")
    email = request.POST.get("email")

    if not first_name or not last_name:
        messages.error(
            request,
            "Nom et prénom sont obligatoires."
        )
        return redirect(request.META.get("HTTP_REFERER", "/"))

    nurse = Person.objects.create(
        role="nurse",
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        email=email.strip() if email else "",
    )

    messages.success(
        request,
        f"Infirmier {nurse} ajouté avec succès."
    )

    return redirect(request.META.get("HTTP_REFERER", "/"))
