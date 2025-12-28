from django.contrib.auth import get_user_model
from .models import Notification

User = get_user_model()


def notify_users(*, users, title, message, object_type="", object_id=None):
    """
    Crée une notification pour une liste d'utilisateurs.

    - users : QuerySet ou liste d'utilisateurs
    - title : titre court
    - message : message détaillé
    - object_type / object_id : lien métier optionnel
    """

    notifications = []

    for user in users:
        notifications.append(
            Notification(
                recipient=user,
                title=title,
                message=message,
                object_type=object_type,
                object_id=object_id,
            )
        )

    Notification.objects.bulk_create(notifications)
