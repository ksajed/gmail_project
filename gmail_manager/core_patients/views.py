from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from .models import Patient
from core_emails.models import Prescription


@login_required
def patient_detail(request, pk):
    """
    Profil patient (lecture seule)
    """
    patient = get_object_or_404(Patient, pk=pk)

    context = {
        "patient": patient,
    }

    return render(
        request,
        "core_patients/patient_detail.html",
        context,
    )


@require_http_methods(["GET", "POST"])
@login_required
def complete_patient(request, patient_id):
    """
    Complétion du patient (nom + téléphone)
    """
    patient = get_object_or_404(Patient, id=patient_id)

    if request.method == "POST":
        patient.full_name = request.POST.get("full_name", "").strip()
        patient.phone_number = request.POST.get("phone_number", "").strip()
        patient.save()

        # 🔁 Redirection vers la dernière ordonnance liée
        prescription = (
            Prescription.objects
            .filter(patient=patient)
            .order_by("-id")
            .first()
        )

        if prescription:
            return redirect(
                "core_emails:prescription_detail",
                pk=prescription.id
            )

        return redirect("core_emails:dashboard")

    return render(
        request,
        "core_patients/complete_patient.html",
        {"patient": patient},
    )
