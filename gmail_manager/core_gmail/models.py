from django.db import models


class GmailMessage(models.Model):
    """
    Email Gmail déjà traité.
    Sert UNIQUEMENT d'anti-doublon IMAP.
    """

    message_id = models.CharField(
        max_length=255,
        unique=True
    )

    subject = models.CharField(
        max_length=255,
        blank=True
    )

    from_email = models.EmailField(
        help_text="Adresse email de l'expéditeur"
    )

    received_at = models.DateTimeField(
        help_text="Date de réception Gmail"
    )

    processed_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date de traitement par l'application"
    )

    def __str__(self):
        return self.subject or self.message_id
