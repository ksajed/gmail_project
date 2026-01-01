# core_emails/models.py
from django.conf import settings
from django.db import models

from core_patients.models import Patient
from .states import PrescriptionStatusEnum


class PrescriptionStatus(models.TextChoices):
    """
    Statuts métier d'une ordonnance
    (alignés sur PrescriptionStatusEnum).
    """
    RECEIVED = PrescriptionStatusEnum.RECEIVED.value, "Ordonnance reçue"
    IN_PROGRESS = PrescriptionStatusEnum.IN_PROGRESS.value, "En cours de préparation"
    READY = PrescriptionStatusEnum.READY.value, "Prête à être délivrée"
    DELIVERED = PrescriptionStatusEnum.DELIVERED.value, "Délivrée"
    BLOCKED = PrescriptionStatusEnum.BLOCKED.value, "Bloquée (problème)"
    ARCHIVED = PrescriptionStatusEnum.ARCHIVED.value, "Archivée"


class SenderType(models.TextChoices):
    """
    Type d'expéditeur (V2 — organisationnel, non médical).
    """
    DOCTOR = "doctor", "Médecin"
    NURSE = "nurse", "Infirmier"
    PATIENT = "patient", "Patient"
    UNKNOWN = "unknown", "Inconnu"


class PrescriptionType(models.TextChoices):
    """
    Type d'ordonnance (V3 — organisationnel, non médical).
    """

    # Noyau obligatoire
    STANDARD = "STANDARD", "Ordonnance classique"
    RENOUVELLEMENT = "RENOUVELLEMENT", "Renouvellement"
    ALD = "ALD", "ALD"
    URGENCE = "URGENCE", "Urgence"
    SORTIE_HOSPITALISATION = "SORTIE_HOSPITALISATION", "Sortie d’hospitalisation"
    DISPOSITIF_MEDICAL = "DISPOSITIF_MEDICAL", "Dispositif médical"
    SOINS_INFIRMIERS = "SOINS_INFIRMIERS", "Soins infirmiers"
    STUPEFIANT = "STUPEFIANT", "Stupéfiants"
    INCOMPLETE = "INCOMPLETE", "Incomplète"
    A_VERIFIER = "A_VERIFIER", "À vérifier"

    # Options
    PSYCHOTROPE = "PSYCHOTROPE", "Psychotrope"
    MEDICAMENT_EXCEPTION = "MEDICAMENT_EXCEPTION", "Médicament d’exception"
    HOSPITALIERE = "HOSPITALIERE", "Hospitalière"
    RESTRICTIVE = "RESTRICTIVE", "Prescription restreinte"
    HORS_AMM = "HORS_AMM", "Hors AMM"

    PEDIATRIQUE = "PEDIATRIQUE", "Pédiatrique"
    PERSONNE_AGEE = "PERSONNE_AGEE", "Personne âgée"
    EHPAD = "EHPAD", "EHPAD"
    HAD = "HAD", "HAD"
    SSIAD = "SSIAD", "SSIAD"

    PANSEMENTS = "PANSEMENTS", "Pansements"
    OXYGENOTHERAPIE = "OXYGENOTHERAPIE", "Oxygénothérapie"
    NUTRITION = "NUTRITION", "Nutrition"
    PERFUSION = "PERFUSION", "Perfusion"
    ORTHOPEDIQUE = "ORTHOPEDIQUE", "Orthopédique"

    VETERINAIRE = "VETERINAIRE", "Vétérinaire"
    ORDONNANCE_ETRANGERE = "ORDONNANCE_ETRANGERE", "Ordonnance étrangère"
    DOM_TOM = "DOM_TOM", "DOM-TOM"
    ESSAI_CLINIQUE = "ESSAI_CLINIQUE", "Essai clinique"
    IMPORTATION = "IMPORTATION", "Importation"

    ILLISIBLE = "ILLISIBLE", "Illisible"
    DUPLICATA = "DUPLICATA", "Duplicata"
    RECTIFICATIVE = "RECTIFICATIVE", "Rectificative"
    BLOQUEE_ADMIN = "BLOQUEE_ADMIN", "Bloquée (administratif)"
    ARCHIVE_PAPIER = "ARCHIVE_PAPIER", "Archivée papier"
    AUTRE = "AUTRE", "Autre"


class Prescription(models.Model):
    """
    Ordonnance reçue par la pharmacie.
    Objet métier central.
    """

    # ===============================
    # STATUT ORDONNANCE (SOURCE UNIQUE)
    # ===============================
    status = models.CharField(
        max_length=20,
        choices=PrescriptionStatus.choices,
        default=PrescriptionStatus.RECEIVED,
    )

    # ===============================
    # TYPE ORDONNANCE (V3 — AJOUT)
    # ===============================
    type = models.CharField(
        max_length=40,
        choices=PrescriptionType.choices,
        default=PrescriptionType.STANDARD,
        help_text="Type organisationnel de l’ordonnance (non médical)",
    )

    # ===============================
    # ORIGINE EMAIL (V2 — ORGANISATIONNEL)
    # ===============================
    sender_type = models.CharField(
        max_length=20,
        choices=SenderType.choices,
        default=SenderType.UNKNOWN,
        help_text="Type d'expéditeur de l'ordonnance (organisationnel)",
    )

    # ===============================
    # LIEN PATIENT (V1 — EMAIL COMME IDENTITÉ)
    # ===============================
    patient = models.ForeignKey(
        Patient,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="prescriptions",
        help_text="Patient lié à l'ordonnance (créé automatiquement si absent)",
    )

    # --------------------
    # TRAÇABILITÉ
    # --------------------
    received_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date de réception de l'ordonnance",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Utilisateur de la pharmacie",
    )

    def __str__(self):
        return f"Ordonnance #{self.id} – {self.get_status_display()}"


class PrescriptionStatusHistory(models.Model):
    """
    Historique légal et opposable
    des changements de statut.
    """

    prescription = models.ForeignKey(
        Prescription,
        on_delete=models.CASCADE,
        related_name="status_history",
    )

    old_status = models.CharField(
        max_length=20,
        choices=PrescriptionStatus.choices,
    )

    new_status = models.CharField(
        max_length=20,
        choices=PrescriptionStatus.choices,
    )

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    changed_at = models.DateTimeField(
        auto_now_add=True,
    )

    comment = models.TextField(
        blank=True,
        help_text="Motif du changement (ex : rupture de stock)",
    )

    def __str__(self):
        return (
            f"Ordonnance #{self.prescription.id} : "
            f"{self.old_status} → {self.new_status}"
        )


# Import V2 (obligatoire pour que Django détecte le modèle)
from .models_assignment import PrescriptionAssignment  # noqa
