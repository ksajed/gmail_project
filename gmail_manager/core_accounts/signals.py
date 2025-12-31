# gmail_manager/core_accounts/signals.py
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Crée automatiquement un UserProfile
    lors de la création d'un utilisateur.
    """
    if created:
        UserProfile.objects.create(user=instance)
