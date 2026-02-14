# core_emails/models.py
from django.conf import settings
from django.db import models

from core_patients.models import Patient
from .states import PrescriptionStatusEnum

from django.db.models.signals import post_save
from django.dispatch import receiver


from django.db.models.signals import pre_save


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
    Type d'expéditeur de l’ordonnance
    (professionnel de santé — usage pharmacie).
    """

    # 🔹 Médecins
    DOCTOR = "doctor", "Médecin"
    DENTIST = "dentist", "Chirurgien-dentiste"
    MIDWIFE = "midwife", "Sage-femme"

    # 🔹 Paramédicaux prescripteurs
    NURSE = "nurse", "Infirmier"
    PHYSIOTHERAPIST = "physiotherapist", "Masseur-kinésithérapeute"
    SPEECH_THERAPIST = "speech_therapist", "Orthophoniste"
    PODIATRIST = "podiatrist", "Pédicure-podologue"

    # 🔹 Compatibilité historique (NE PAS SUPPRIMER)
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
    
    
    # ================================================================
    # DONNÉES MÉDICALES (EXTRAIT MINIMAL),date de l’établissement ordo
    # ================================================================
    established_at = models.DateField(
        null=True,
        blank=True,
        help_text="Date d’établissement de l’ordonnance (date médecin) — base des calculs de renouvellement",
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

# =====================================================
# HISTORIQUE DES CHANGEMENTS DE STATUT
# =====================================================
    @property
    def assigned_nurse(self):
        """Compat: retourne l'infirmier affecté via PrescriptionAssignment si présent."""
        a = getattr(self, "assignment", None)
        if not a:
            return None
        return getattr(a, "nurse", None)

    @property
    def has_assigned_nurse(self) -> bool:
        return self.assigned_nurse is not None

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

# =====================================================
# INFORMATIONS DE RENOUVELLEMENT
# =====================================================
class PrescriptionRenewalInfo(models.Model):
    prescription = models.OneToOneField(
        Prescription,
        on_delete=models.CASCADE,
        related_name="renewal_info",
    )

    # nombre de renouvellements autorisés (0,1,2,...)
    renewal_times = models.PositiveSmallIntegerField(default=0)

    # durée d’une période (par défaut 30 jours)
    period_days = models.PositiveSmallIntegerField(default=30)

        # nombre de renouvellements déjà réalisés (0..renewal_times)
    renewal_done_count = models.PositiveSmallIntegerField(default=0)

    # date/heure du dernier renouvellement réalisé
    last_renewal_ordered_at = models.DateTimeField(null=True, blank=True)

    
    # contact médecin
    doctor_email = models.EmailField(blank=True)
    doctor_name = models.CharField(max_length=120, blank=True)

    # états après envoi
    reminder_5_patient_email_sent_at = models.DateTimeField(null=True, blank=True)
    reminder_5_patient_sms_sent_at = models.DateTimeField(null=True, blank=True)
    reminder_3_patient_email_sent_at = models.DateTimeField(null=True, blank=True)
    reminder_3_patient_sms_sent_at = models.DateTimeField(null=True, blank=True)
    doctor_email_sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"RenewalInfo({self.prescription_id})"









# =====================================================
# HISTORIQUE DES RENOUVELLEMENTS RÉALISÉS (V7)
# =====================================================
class PrescriptionRenewalEvent(models.Model):
    prescription = models.ForeignKey(
        Prescription,
        on_delete=models.CASCADE,
        related_name="renewal_events",
    )
    number = models.PositiveSmallIntegerField()  # 1..N (ordre du renouvellement)
    ordered_at = models.DateTimeField(auto_now_add=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_renewal_events",
    )
    note = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-ordered_at"]
        unique_together = [("prescription", "number")]

    def __str__(self):
        return f"RenewalEvent(p={self.prescription_id}, n={self.number})"


# =====================================================
# 🔍 TRACEUR TEMPORAIRE — QUI ÉCRASE Prescription.type ?
# =====================================================


@receiver(pre_save, sender=Prescription)
def trace_prescription_type(sender, instance, **kwargs):
    if not instance.pk:
        return

    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old.type != instance.type:
        print("🔥 TYPE CHANGE DETECTED 🔥")
        print("PK:", instance.pk)
        print("OLD TYPE:", old.type)
        print("NEW TYPE:", instance.type)


# =====================================================
# CRÉATION AUTOMATIQUE DES INFOS DE RENOUVELLEMENT
# =====================================================
@receiver(post_save, sender=Prescription)
def ensure_renewal_info(sender, instance, created, **kwargs):
    if instance.type == PrescriptionType.RENOUVELLEMENT:
        PrescriptionRenewalInfo.objects.get_or_create(prescription=instance)


# =====================================================
# 🔔 PARAMÉTRAGE NOTIFICATIONS PAR ORDONNANCE (V8)
# =====================================================

class PrescriptionNotificationSettings(models.Model):
    prescription = models.OneToOneField(
        Prescription,
        on_delete=models.CASCADE,
        related_name="notification_settings"
    )

    patient_channel = models.CharField(
        max_length=10,
        choices=[
            ("NONE", "NONE"),
            ("SMS", "SMS"),
            ("EMAIL", "EMAIL"),
            ("BOTH", "BOTH"),
        ],
        default="NONE"
    )

    nurse_channel = models.CharField(
        max_length=10,
        choices=[
            ("NONE", "NONE"),
            ("SMS", "SMS"),
            ("EMAIL", "EMAIL"),
            ("BOTH", "BOTH"),
        ],
        default="NONE",
    )

    # Message libre (RGPD-safe) ajouté au SMS/email si canal activé
    free_text_message = models.TextField(
        blank=True,
        default="",
        help_text="Message libre optionnel ajouté aux notifications (sans données médicales).",
    )

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"NotificationSettings(prescription={self.prescription_id})"


class PrescriptionNotificationEvent(models.Model):
    prescription = models.ForeignKey(
        Prescription,
        on_delete=models.CASCADE,
        related_name="notification_events"
    )

    recipient_type = models.CharField(
        max_length=10,
        choices=[
            ("PATIENT", "PATIENT"),
            ("NURSE", "NURSE"),
        ]
    )

    channel = models.CharField(
        max_length=10,
        choices=[
            ("NONE", "NONE"),
            ("SMS", "SMS"),
            ("EMAIL", "EMAIL"),
            ("BOTH", "BOTH"),
        ]
    )

    destination = models.CharField(max_length=255)

    result = models.CharField(
        max_length=10,
        choices=[
            ("SENT", "SENT"),
            ("FAILED", "FAILED"),
            ("SKIPPED", "SKIPPED"),
        ]
    )

    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_notification_events",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"NotificationEvent("
            f"p={self.prescription_id}, "
            f"{self.recipient_type}, "
            f"{self.channel}, "
            f"{self.result}"
            f")"
        )
