# gmail_manager/core_attachments/models.py
from django.conf import settings
from django.db import models

# Import du modèle Prescription (ordonnance)
from core_emails.models import Prescription


class PrescriptionAttachment(models.Model):
    """
    Représente un fichier joint à une ordonnance.
    Exemple : photo prise par le patient, PDF scanné, image WhatsApp, etc.
    """

    # -----------------------------
    # LIEN AVEC L'ORDONNANCE
    # -----------------------------
    prescription = models.ForeignKey(
        Prescription,
        on_delete=models.CASCADE,
        related_name="attachments"
    )

    # -----------------------------
    # FICHIER PHYSIQUE
    # -----------------------------
    file = models.FileField(
        upload_to="prescriptions/",
        help_text="Fichier de l'ordonnance (PDF, photo, scan)"
    )

    # -----------------------------
    # MÉTADONNÉES DU FICHIER
    # -----------------------------
    original_filename = models.CharField(
        max_length=255,
        help_text="Nom original du fichier envoyé"
    )

    mime_type = models.CharField(
        max_length=100,
        help_text="Type MIME du fichier"
    )

    # -----------------------------
    # TRAÇABILITÉ
    # -----------------------------
    uploaded_at = models.DateTimeField(auto_now_add=True)

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    # =============================
    # HELPERS MÉTIER (AJOUTÉS)
    # =============================

    @property
    def extension(self):
        return self.original_filename.lower().split(".")[-1]

    @property
    def is_pdf(self):
        return self.mime_type == "application/pdf" or self.extension == "pdf"

    @property
    def is_image(self):
        return self.mime_type.startswith("image/") or self.extension in {
            "jpg", "jpeg", "png", "webp"
        }

    def __str__(self):
        return self.original_filename


class PrescriptionAttachmentAccess(models.Model):
    """
    Trace chaque accès à un fichier d'ordonnance.
    OBLIGATOIRE en contexte médical (audit, RGPD, litige).
    """

    # Fichier consulté ou téléchargé
    attachment = models.ForeignKey(
        PrescriptionAttachment,
        on_delete=models.CASCADE,
        related_name="access_logs"
    )

    # Utilisateur ayant accédé au fichier
    accessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    # Date et heure exactes de l'accès
    accessed_at = models.DateTimeField(
        auto_now_add=True
    )

    # Type d'action effectuée sur le fichier
    action = models.CharField(
        max_length=20,
        choices=[
            ("VIEW", "Consultation"),
            ("DOWNLOAD", "Téléchargement"),
        ]
    )

    def __str__(self):
        return f"{self.attachment} - {self.action}"
