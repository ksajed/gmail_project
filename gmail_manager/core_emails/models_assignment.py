from django.db import models

from core_patients.models import Patient
from core_people.models import Person

from .models import Prescription


class PrescriptionAssignment(models.Model):
    """
    Affectation organisationnelle V2
    Ordonnance ↔ Infirmier ↔ Patient

    ⚠️ Aucune valeur médicale
    ⚠️ 1 ordonnance = 1 affectation max
    """

    prescription = models.OneToOneField(
        Prescription,
        on_delete=models.CASCADE,
        related_name="assignment",
        help_text="Ordonnance concernée",
    )

    nurse = models.ForeignKey(
        Person,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_prescriptions",
        help_text="Infirmier associé (organisationnel)",
    )

    patient = models.ForeignKey(
        Patient,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_prescriptions",
        help_text="Patient concerné (optionnel)",
    )

    assigned_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date d'affectation",
    )

    class Meta:
        verbose_name = "Affectation ordonnance"
        verbose_name_plural = "Affectations ordonnances"

    def __str__(self):
        return f"Affectation ordonnance #{self.prescription.id}"
