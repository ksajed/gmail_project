from django import template
from django.utils import timezone

register = template.Library()


# ============================
# STATUT ORDONNANCE → CSS
# ============================
@register.simple_tag
def prescription_status_class(status):
    """
    Retourne la classe CSS correspondant au statut d'une ordonnance.
    """
    if status in ("PENDING", "RECEIVED"):
        return "status-pending"
    if status == "IN_PROGRESS":
        return "status-progress"
    if status in ("VALIDATED", "DELIVERED"):
        return "status-valid"
    if status in ("REJECTED", "CANCELLED"):
        return "status-rejected"
    if status == "ARCHIVED":
        return "status-archived"
    return ""


# ============================
# PRIORITÉ TEMPORELLE (PRO)
# ============================
@register.filter
def time_since_label(value):
    """
    Texte lisible côté métier :
    - 'il y a 5 min'
    - 'il y a 1 h'
    """
    if not value:
        return ""

    now = timezone.now()
    delta = now - value
    minutes = int(delta.total_seconds() // 60)

    if minutes < 60:
        return f"il y a {minutes} min"

    hours = minutes // 60
    return f"il y a {hours} h"


@register.filter
def time_priority_class(value):
    """
    Classe CSS selon la priorité temporelle.

    🟢 < 30 min      → time-ok
    🟠 30 min – 2 h  → time-warning
    🔴 > 2 h         → time-urgent
    """
    if not value:
        return ""

    now = timezone.now()
    delta = now - value
    minutes = int(delta.total_seconds() // 60)

    if minutes < 30:
        return "time-ok"
    elif minutes < 120:
        return "time-warning"
    return "time-urgent"
