#core_emails/models.py
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
        # ⚠️ DOIT TOUJOURS FONCTIONNER
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
