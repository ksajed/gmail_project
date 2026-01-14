# gmail_manager/core_notifications/models.py
from django.conf import settings
from django.db import models

from django.conf import settings
from django.db import models
from django.utils import timezone



class Notification(models.Model):
    """
    Notification interne pour les utilisateurs de la pharmacie.
    """

    # -----------------------------
    # DESTINATAIRE
    # -----------------------------
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    # -----------------------------
    # CONTENU
    # -----------------------------
    title = models.CharField(
        max_length=255,
        help_text="Titre court de la notification"
    )

    message = models.TextField(
        help_text="Message détaillé"
    )

    # -----------------------------
    # ÉTAT
    # -----------------------------
    is_read = models.BooleanField(
        default=False,
        help_text="Notification lue ou non"
    )

    # -----------------------------
    # MÉTADONNÉES
    # -----------------------------
    created_at = models.DateTimeField(
        auto_now_add=True
    )

    # Lien optionnel vers un objet métier (ex : ordonnance)
    object_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Type d'objet lié (ex : Prescription)"
    )

    object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="ID de l'objet lié"
    )

    def __str__(self):
        status = "LU" if self.is_read else "NON LU"
        return f"[{status}] {self.title}"
# -----------------------------
# SMS (logs + templates)
# -----------------------------

class SmsPurpose(models.TextChoices):
    STATUS_UPDATE = "STATUS_UPDATE", "Status update"
    RENEWAL = "RENEWAL", "Renewal"
    INFO = "INFO", "Info"


class SmsProvider(models.TextChoices):
    OVH = "OVH", "OVH"


class SmsStatus(models.TextChoices):
    QUEUED = "QUEUED", "Queued"
    SENT = "SENT", "Sent"
    FAILED = "FAILED", "Failed"


class SmsTemplate(models.Model):
    key = models.CharField(max_length=100, unique=True)
    language = models.CharField(max_length=10, default="fr")
    content = models.TextField()
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.key} ({self.language})"


class SmsMessage(models.Model):
    recipient_phone = models.CharField(max_length=32)  # E.164: +33...
    purpose = models.CharField(max_length=30, choices=SmsPurpose.choices)
    template_key = models.CharField(max_length=100, blank=True, default="")
    rendered_text = models.TextField()

    provider = models.CharField(max_length=20, choices=SmsProvider.choices, default=SmsProvider.OVH)
    provider_message_id = models.CharField(max_length=120, blank=True, default="")

    status = models.CharField(max_length=20, choices=SmsStatus.choices, default=SmsStatus.QUEUED)
    last_error_message = models.TextField(blank=True, default="")

    related_prescription = models.ForeignKey(
        "core_emails.Prescription",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_messages",
    )

    created_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.purpose} -> {self.recipient_phone} ({self.status})"


class SmsAttempt(models.Model):
    sms_message = models.ForeignKey(SmsMessage, on_delete=models.CASCADE, related_name="attempts")
    attempt_no = models.PositiveIntegerField(default=1)
    requested_at = models.DateTimeField(default=timezone.now)
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True, default="")
    response_payload = models.JSONField(blank=True, null=True)

    def __str__(self) -> str:
        return f"Attempt {self.attempt_no} for SMS {self.sms_message_id} ({'OK' if self.success else 'FAIL'})"
