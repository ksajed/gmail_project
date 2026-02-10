from django.db import models


class Person(models.Model):
    """
    Référentiel de personnes externes à l'officine.
    Usage organisationnel uniquement (V2).
    """

    ROLE_CHOICES = (
        ("doctor", "Médecin"),
        ("nurse", "Infirmier"),
        ("patient", "Patient"),
        ("other", "Autre"),
    )

    first_name = models.CharField(
        max_length=100,
        blank=True,
    )

    last_name = models.CharField(
        max_length=100,
        blank=True,
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        help_text="Rôle organisationnel",
    )

    email = models.EmailField(
        blank=True,
    )

    phone = models.CharField(
        max_length=30,
        blank=True,
    )


    @property
    def phone_number(self) -> str:
        """Compat: alias de 'phone' (certains modules utilisent phone_number)."""
        return (self.phone or "").strip()

    @phone_number.setter
    def phone_number(self, value: str) -> None:
        self.phone = (value or "").strip()
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Personne"
        verbose_name_plural = "Personnes"

    def __str__(self):
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return f"Personne #{self.id}"
