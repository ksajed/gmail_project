from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .models import Prescription
from core_notifications.services import notify_users

User = get_user_model()


@receiver(post_save, sender=Prescription)
def notify_prescription_received(sender, instance, created, **kwargs):
    """
    Notification automatique lors de la création d'une ordonnance.
    Version V1 — pharmacie unique, sans données patient.
    """
    if not created:
        return

    users = User.objects.all()

    notify_users(
        users=users,
        title="Nouvelle ordonnance reçue",
        message=f"Une nouvelle ordonnance (ID #{instance.id}) a été reçue.",
        object_type="Prescription",
        object_id=instance.id,
    )
