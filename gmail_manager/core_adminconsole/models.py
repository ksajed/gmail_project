from __future__ import annotations
from django.conf import settings
from django.db import models

class AdminAuditEvent(models.Model):
    class Action(models.TextChoices):
        LOGIN = "LOGIN", "Connexion admin"
        ACCOUNT_DISABLE = "ACCOUNT_DISABLE", "Mise en veille compte"
        ACCOUNT_ENABLE = "ACCOUNT_ENABLE", "Réactivation compte"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="admin_audit_events"
    )
    action = models.CharField(max_length=64, choices=Action.choices)
    target_type = models.CharField(max_length=64, blank=True, default="")
    target_id = models.CharField(max_length=64, blank=True, default="")
    summary = models.CharField(max_length=255, blank=True, default="")
    metadata = models.JSONField(blank=True, default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action} {self.summary}"
