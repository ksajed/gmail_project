"""
ORDO V9 - Moteur de templates pour les notifications de renouvellement.

Ce fichier est volontairement isolé :
- aucune modification des vues dans ce lot ;
- aucune modification du dashboard ;
- aucune modification du workflow ;
- aucun impact sur le moteur de cycles V8.

Objectif :
rendre les SMS et Emails de renouvellement configurables via RenewalNotificationTemplate.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from django.utils import timezone

from .models import RenewalNotificationTemplate, RenewalSettings


CHANNEL_SMS = "SMS"
CHANNEL_EMAIL = "EMAIL"


def get_active_template(channel: str) -> Optional[RenewalNotificationTemplate]:
    """
    Retourne le premier template actif pour un canal donné.

    channel attendu :
    - "SMS"
    - "EMAIL"

    Retourne None si aucun template actif n'est trouvé.
    """
    if not channel:
        return None

    normalized_channel = str(channel).upper().strip()

    return (
        RenewalNotificationTemplate.objects
        .filter(channel=normalized_channel, active=True)
        .order_by("id")
        .first()
    )


def _safe_get_patient_name(prescription: Any) -> str:
    """
    Récupère un nom patient sans hypothèse forte sur le modèle Patient.

    Cette fonction évite les erreurs si certains champs n'existent pas.
    """
    patient = getattr(prescription, "patient", None)
    if not patient:
        return ""

    candidates = [
        "full_name",
        "name",
        "display_name",
        "nom",
    ]

    for attr in candidates:
        value = getattr(patient, attr, None)
        if callable(value):
            try:
                value = value()
            except TypeError:
                value = None
        if value:
            return str(value)

    first_name = getattr(patient, "first_name", "") or ""
    last_name = getattr(patient, "last_name", "") or ""
    combined = f"{first_name} {last_name}".strip()
    if combined:
        return combined

    return str(patient) if str(patient) else ""


def _safe_format_date(value: Any) -> str:
    """
    Formate une date de manière sûre.
    """
    if not value:
        return ""

    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y")

    return str(value)


def _get_renewal_settings() -> Optional[RenewalSettings]:
    """
    Retourne la configuration renouvellements si elle existe.
    """
    return RenewalSettings.objects.order_by("id").first()


def _get_due_date(prescription: Any, cycle: Any = None) -> str:
    """
    Récupère l'échéance la plus probable.

    On reste volontairement défensif car le modèle existant peut évoluer.
    """
    candidates = []

    if cycle is not None:
        candidates.extend([
            getattr(cycle, "due_date", None),
            getattr(cycle, "expected_due_date", None),
            getattr(cycle, "next_due_date", None),
        ])

    renewal_info = getattr(prescription, "renewal_info", None)
    if renewal_info is not None:
        candidates.extend([
            getattr(renewal_info, "next_due_date", None),
            getattr(renewal_info, "due_date", None),
        ])

    candidates.extend([
        getattr(prescription, "next_due_date", None),
        getattr(prescription, "due_date", None),
    ])

    for value in candidates:
        if value:
            return _safe_format_date(value)

    return ""


def _get_cycle_number(cycle: Any = None) -> str:
    """
    Retourne le numéro du cycle courant si disponible.
    """
    if cycle is None:
        return ""

    for attr in ["cycle_number", "number", "renewal_number"]:
        value = getattr(cycle, attr, None)
        if value is not None:
            return str(value)

    return ""


def _get_cycles_restants(prescription: Any, cycle: Any = None) -> str:
    """
    Calcule une valeur indicative des cycles restants si les champs existent.

    Important :
    Cette fonction ne modifie rien.
    Elle ne touche pas aux compteurs métier existants.
    """
    renewal_info = getattr(prescription, "renewal_info", None)

    total = None
    done = None

    if renewal_info is not None:
        total = getattr(renewal_info, "renewal_times", None)
        done = getattr(renewal_info, "renewal_done_count", None)

    if total is None:
        total = getattr(prescription, "renewal_times", None)

    if done is None:
        done = getattr(prescription, "renewal_done_count", None)

    try:
        if total is not None and done is not None:
            remaining = int(total) - int(done)
            return str(max(remaining, 0))
    except (TypeError, ValueError):
        return ""

    return ""


def build_renewal_context(
    prescription: Any,
    cycle: Any = None,
    extra_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    Construit le contexte disponible pour les templates.

    Variables supportées :
    - numero_ordo
    - nom_patient
    - date_echeance
    - cycle_actuel
    - cycles_restants
    - nom_pharmacie
    - telephone_pharmacie

    Règle absolue :
    numero_ordo doit rester au format #ID, exemple #409.
    """
    settings = _get_renewal_settings()

    prescription_id = getattr(prescription, "id", None) or getattr(prescription, "pk", "")
    numero_ordo = f"#{prescription_id}" if prescription_id else ""

    context: Dict[str, str] = {
        "numero_ordo": numero_ordo,
        "nom_patient": _safe_get_patient_name(prescription),
        "date_echeance": _get_due_date(prescription, cycle=cycle),
        "cycle_actuel": _get_cycle_number(cycle),
        "cycles_restants": _get_cycles_restants(prescription, cycle=cycle),
        "nom_pharmacie": getattr(settings, "pharmacy_name", "") if settings else "",
        "telephone_pharmacie": getattr(settings, "phone", "") if settings else "",
    }

    if extra_context:
        for key, value in extra_context.items():
            context[str(key)] = "" if value is None else str(value)

    return context


def _safe_render(text: str, context: Dict[str, str]) -> str:
    """
    Remplace les variables connues.

    Les variables inconnues restent visibles telles quelles.
    Cela évite de faire planter l'envoi si un modèle contient une variable non supportée.
    """
    if not text:
        return ""

    rendered = str(text)

    for key, value in context.items():
        rendered = rendered.replace("{" + key + "}", value or "")

    return rendered


def render_renewal_template(
    template: RenewalNotificationTemplate,
    prescription: Any,
    cycle: Any = None,
    extra_context: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """
    Rend un template et retourne :

    (subject, body)

    Pour SMS :
    - subject sera une chaîne vide.

    Pour EMAIL :
    - subject et body sont rendus.
    """
    context = build_renewal_context(
        prescription=prescription,
        cycle=cycle,
        extra_context=extra_context,
    )

    subject = _safe_render(getattr(template, "subject", "") or "", context)
    body = _safe_render(getattr(template, "body", "") or "", context)

    return subject, body


def render_renewal_message(
    channel: str,
    prescription: Any,
    cycle: Any = None,
    extra_context: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str, Optional[RenewalNotificationTemplate]]:
    """
    Fonction pratique pour les futures vues SMS / Email.

    Retourne :

    (subject, body, template)

    Si aucun template actif n'existe :
    - subject = ""
    - body = ""
    - template = None
    """
    template = get_active_template(channel)
    if template is None:
        return "", "", None

    subject, body = render_renewal_template(
        template=template,
        prescription=prescription,
        cycle=cycle,
        extra_context=extra_context,
    )

    return subject, body, template
