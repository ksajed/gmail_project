from __future__ import annotations

from django.conf import settings
from django.db import models


class AdminAuditEvent(models.Model):
    """Journal append-only des actions Admin Console (style SaaS).

    Objectif:
    - traçabilité (qui / quoi / quand / où)
    - recherches (action, acteur, cible, texte)
    - compat évolutive (metadata JSON)
    """

    class Action(models.TextChoices):
        # Générique
        LOGIN = "LOGIN", "Connexion admin"
        EXPORT_CSV = "EXPORT_CSV", "Export CSV"

        # Comptes
        ACCOUNT_DISABLE = "ACCOUNT_DISABLE", "Mise en veille compte"
        ACCOUNT_ENABLE = "ACCOUNT_ENABLE", "Réactivation compte"

        # Infirmiers (mandataires)
        CREATE_NURSE = "CREATE_NURSE", "Création infirmier"
        EDIT_NURSE = "EDIT_NURSE", "Édition infirmier"
        UPDATE_NURSE = "UPDATE_NURSE", "Mise à jour infirmier"
        DEACTIVATE_NURSE = "DEACTIVATE_NURSE", "Désactivation infirmier"
        ACTIVATE_NURSE = "ACTIVATE_NURSE", "Réactivation infirmier"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_audit_events",
    )

    # On garde choices pour UI/filtre, mais action reste stockée en string
    action = models.CharField(max_length=64, choices=Action.choices)

    target_type = models.CharField(max_length=64, blank=True, default="")
    target_id = models.CharField(max_length=64, blank=True, default="")

    summary = models.CharField(max_length=255, blank=True, default="")

    # Best-effort (proxy / reverse-proxy / local)
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP source (best-effort)",
    )

    # Best-effort, tronqué côté service
    user_agent = models.TextField(
        blank=True,
        help_text="User-Agent (best-effort)",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Données structurées (JSON) pour analyses/forensics",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

        permissions = [
            ("access_console", "Accéder à l'Admin Console"),
            ("manage_accounts", "Gérer les comptes"),
            ("manage_groups", "Gérer les groupes et permissions"),
            ("view_audit", "Voir l'audit"),
            ("clear_audit", "Purger l'audit"),
        ]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action} {self.summary}"
