from django.conf import settings
from django.db import models


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
