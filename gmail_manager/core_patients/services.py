# gmail_manager/core_patients/services.py
from .models import Patient


def get_or_create_patient_from_email(email: str) -> Patient:
    """
    Récupère un patient par email normalisé, ou le crée automatiquement.

    V1 : l'email sert d'identifiant patient principal.
    - normalisation (strip + lowercase)
    - évite les doublons invisibles
    """

    # 🔒 Normalisation email (CRITIQUE)
    normalized_email = (email or "").strip().lower()

    if not normalized_email:
        raise ValueError("Email patient vide ou invalide")

    # 🔍 Recherche insensible à la casse
    patient = Patient.objects.filter(
        email__iexact=normalized_email
    ).first()

    if patient:
        # 🔁 Sécurité : on normalise l’email stocké si besoin
        if patient.email != normalized_email:
            patient.email = normalized_email
            patient.save(update_fields=["email"])
        return patient

    # ➕ Création unique
    return Patient.objects.create(
        email=normalized_email,
        full_name="",
        phone_number="",
    )
