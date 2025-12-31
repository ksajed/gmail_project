# gmail_manager/core_accounts/models.py
from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    """
    Extension professionnelle du User Django.
    Contient les rôles et préférences utilisateur.
    """

    ROLE_ADMIN = "ADMIN"
    ROLE_USER = "USER"

    ROLE_CHOICES = [
        (ROLE_ADMIN, "Administrateur"),
        (ROLE_USER, "Utilisateur"),
    ]

    PER_PAGE_10 = 10
    PER_PAGE_25 = 25
    PER_PAGE_50 = 50

    PER_PAGE_CHOICES = [
        (PER_PAGE_10, "10 lignes"),
        (PER_PAGE_25, "25 lignes"),
        (PER_PAGE_50, "50 lignes"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_USER,
    )

    # ✅ PRÉFÉRENCE UTILISATEUR — lignes par page
    per_page = models.PositiveSmallIntegerField(
        choices=PER_PAGE_CHOICES,
        default=PER_PAGE_10,
        help_text="Nombre de lignes affichées par page dans les listes",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"
