from django.db import models


class Patient(models.Model):
    """
    Patient pharmacie V1
    Créé automatiquement depuis une ordonnance si nécessaire.
    """

    full_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Nom du patient (optionnel en V1)"
    )

    email = models.EmailField(
        unique=True,
        help_text="Email principal du patient (identité V1)"
    )

    phone_number = models.CharField(
        max_length=30,
        blank=True,
        help_text="Numéro de téléphone (optionnel en V1)"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    # ==================================================
    # ✅ RÈGLE MÉTIER OFFICIELLE — PATIENT COMPLET
    # ==================================================
    @property
    def is_complete(self) -> bool:
        """
        Un patient est considéré comme COMPLET si :
        - email présent (toujours vrai en V1)
        - nom renseigné
        - téléphone renseigné
        """
        return bool(
            self.email
            and self.full_name
            and self.phone_number
        )

    def __str__(self):
        return self.full_name or self.email
