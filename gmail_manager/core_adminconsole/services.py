from typing import Any
from django.http import HttpRequest
from .models import AdminAuditEvent

def get_client_ip(request: HttpRequest) -> str | None:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")

def audit(
    request: HttpRequest,
    *,
    action: str,
    summary: str = "",
    target_type: str = "",
    target_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    AdminAuditEvent.objects.create(
        actor=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
        action=action,
        summary=summary,
        target_type=target_type,
        target_id=str(target_id or ""),
        metadata=metadata or {},
        ip_address=get_client_ip(request),
    )


# --- ADMINCONSOLE_AUDIT_SERVICE_V2:BEGIN ---
from typing import Any, Dict, Optional

from django.utils import timezone

from .models import AdminAuditEvent


def _get_ip(request) -> str:
    try:
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            # premier IP = client
            return (xff.split(",")[0] or "").strip()
        return (request.META.get("REMOTE_ADDR") or "").strip()
    except Exception:
        return ""


def audit(
    request,
    action: str,
    summary: str,
    target_type: str = "",
    target_id: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Audit append-only, structuré (niveau SaaS).

    - action: code (string ou TextChoices)
    - summary: phrase courte humaine
    - target_type/target_id: cible (Person/User/Prescription/etc.)
    - metadata: dict JSON (optionnel)
    """
    try:
        actor = getattr(request, "user", None)
        if actor and not getattr(actor, "is_authenticated", False):
            actor = None
    except Exception:
        actor = None

    ip = _get_ip(request)
    ua = ""
    try:
        ua = (request.META.get("HTTP_USER_AGENT") or "")[:2000]
    except Exception:
        ua = ""

    AdminAuditEvent.objects.create(
        action=str(action),
        summary=str(summary)[:255],
        target_type=str(target_type or "")[:100],
        target_id=str(target_id or "")[:100],
        actor=actor,
        ip_address=ip or None,
        user_agent=ua,
        metadata=metadata or {},
        created_at=timezone.now() if hasattr(AdminAuditEvent, "created_at") else None,
    )
# --- ADMINCONSOLE_AUDIT_SERVICE_V2:END ---



# --- ADMINCONSOLE_IAM_V2:BEGIN ---
from django.contrib.auth.models import User
from django.db import transaction

def _is_last_superuser(target: User) -> bool:
    if not target.is_superuser:
        return False
    # dernier superuser actif ?
    return User.objects.filter(is_superuser=True, is_active=True).exclude(pk=target.pk).count() == 0

@transaction.atomic
def soft_delete_user(*, actor: User, target: User) -> None:
    """Suppression logique SaaS:
    - is_active=False
    - retrait groupes + permissions directes (sécurité)
    - garde-fous: impossible sur soi-même, impossible sur dernier superuser actif
    """
    if actor.pk == target.pk:
        raise ValueError("Impossible de mettre en veille son propre compte.")
    if _is_last_superuser(target):
        raise ValueError("Impossible de mettre en veille le dernier superuser actif.")

    target.is_active = False
    target.save(update_fields=["is_active"])

    # en mode SaaS: on retire les droits lors de la mise en veille
    target.groups.clear()
    target.user_permissions.clear()

@transaction.atomic
def reactivate_user(*, actor: User, target: User) -> None:
    """Réactivation sans restauration automatique des groupes/perms."""
    if actor.pk == target.pk and not target.is_active:
        # autorisé à se réactiver ? en général non nécessaire; on laisse simple
        pass
    target.is_active = True
    target.save(update_fields=["is_active"])
# --- ADMINCONSOLE_IAM_V2:END ---



# --- ADMINCONSOLE_ANTILOCK_V3:BEGIN ---
from django.contrib.auth.models import Group, Permission, User

def _count_active_superusers_excluding(user: User) -> int:
    return User.objects.filter(is_superuser=True, is_active=True).exclude(pk=user.pk).count()

def guard_not_last_superuser_change(*, target: User, will_be_superuser: bool) -> None:
    """Refuse de retirer superuser si target est le dernier superuser actif."""
    if target.is_superuser and (not will_be_superuser) and target.is_active:
        if _count_active_superusers_excluding(target) == 0:
            raise ValueError("Refus: impossible de retirer le statut superuser (dernier superuser actif).")

def guard_not_last_superuser_deactivate(*, target: User, will_be_active: bool) -> None:
    if target.is_superuser and target.is_active and (not will_be_active):
        if _count_active_superusers_excluding(target) == 0:
            raise ValueError("Refus: impossible de désactiver le dernier superuser actif.")

def guard_self_lockout(*, actor: User, new_is_active: bool | None = None, new_is_superuser: bool | None = None) -> None:
    """Empêche un admin de se bloquer lui-même.
    Minimal V3:
      - interdire de se mettre inactive via la console
      - interdire de se retirer superuser si c'est lui-même et dernier superuser
    """
    if new_is_active is not None and actor.is_active and (not new_is_active):
        raise ValueError("Refus: impossible de désactiver son propre compte via l'Admin Console.")
    if new_is_superuser is not None:
        guard_not_last_superuser_change(target=actor, will_be_superuser=new_is_superuser)
# --- ADMINCONSOLE_ANTILOCK_V3:END ---

