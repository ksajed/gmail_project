# core_emails/timeline.py
from __future__ import annotations


import re

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from django.utils import timezone



from core_emails.labels import status_fr, origin_fr, prescription_type_fr

@dataclass(frozen=True)
class TimelineEvent:
    uid: str
    ts: Any

    actor_label: str
    actor_sub: str

    kind: str
    icon: str
    tone: str

    title: str
    subtitle: str

    chips: List[Dict[str, str]]
    details: List[str]

    tech: Optional[Dict[str, Any]] = None


def _safe_username(user) -> str:
    if not user:
        return "Système"
    return getattr(user, "username", None) or getattr(user, "email", None) or "Système"


def _upper(s: str) -> str:
    return (s or "").upper()


def _tone_kind_icon_from_status(new_status: str) -> tuple[str, str, str]:
    ns = _upper(str(new_status))

    tone = "neutral"
    kind = "status"
    icon = "repeat"

    if "ARCHIV" in ns:
        return "neutral", "archive", "archive"
    if "DELIVER" in ns or "LIVR" in ns:
        return "success", "status", "truck"
    if "READY" in ns or "PRET" in ns:
        return "info", "status", "check-circle"
    if "IN_PROGRESS" in ns or "EN_COURS" in ns:
        return "info", "status", "activity"
    if "RECEIV" in ns or "RECU" in ns:
        return "info", "status", "inbox"
    if "REJECT" in ns or "REJET" in ns:
        return "danger", "warning", "x-circle"
    if "BLOCK" in ns or "BLOQ" in ns:
        return "danger", "warning", "alert-triangle"

    return tone, kind, icon


def _chips_from_comment(comment: str) -> List[Dict[str, str]]:
    c = _upper(comment or "")
    chips: List[Dict[str, str]] = []

    if "SMS=SKIPPED" in c:
        chips.append({"label": "SMS: ignoré", "tone": "neutral"})
    if "EMAIL=SKIPPED" in c:
        chips.append({"label": "Email: ignoré", "tone": "neutral"})
    if "SMS=SENT" in c or "SMS=OK" in c:
        chips.append({"label": "SMS: envoyé", "tone": "success"})
    if "EMAIL=SENT" in c or "EMAIL=OK" in c:
        chips.append({"label": "Email: envoyé", "tone": "success"})
    return chips
# ORDO_TIMELINE_HELPERS_V1:BEGIN
def _parse_notification_settings_comment(raw: str) -> dict:
    """Parse des traces 'Paramétrage notifications mis à jour' / 'Notif: PATIENT=...' (best-effort).

    Retour: dict {patient: str|None, nurse: str|None} avec valeurs normalisées (upper).
    Ne lève jamais.
    """
    try:
        s = (raw or "").strip()
        if not s:
            return {"patient": None, "nurse": None}

        up = s.upper()

        # Exemples possibles observés:
        # - "Paramétrage notifications mis à jour : patient=NONE, infirmier=NONE"
        # - "Notif: PATIENT=NONE ; NURSE=NONE ..."
        # - variations espaces/; , etc.
        patient = None
        nurse = None

        # PATIENT=XXX
        m = re.search(r"\bPATIENT\s*=\s*([A-Z_]+)\b", up)
        if m:
            patient = m.group(1)

        # NURSE=XXX / INFIRMIER=XXX
        m = re.search(r"\bNURSE\s*=\s*([A-Z_]+)\b", up)
        if m:
            nurse = m.group(1)
        else:
            m = re.search(r"\bINFIRMIER\s*=\s*([A-Z_]+)\b", up)
            if m:
                nurse = m.group(1)

        # fallback "patient=NONE" / "infirmier=NONE"
        if patient is None:
            m = re.search(r"\bPATIENT\s*=\s*([A-Z_]+)\b", up)
            if m:
                patient = m.group(1)
            else:
                m = re.search(r"\bPATIENT\s*=\s*([A-Z_]+)\b", up)
        if patient is None:
            m = re.search(r"\bPATIENT\s*=\s*([A-Z_]+)\b", up)

        if patient is None:
            m = re.search(r"\bPATIENT\s*=\s*([A-Z_]+)\b", up)

        if patient is None:
            m = re.search(r"\bPATIENT\s*=\s*([A-Z_]+)\b", up)

        # "patient=NONE" (lowercase possible)
        if patient is None:
            m = re.search(r"\bPATIENT\s*=\s*([A-Z_]+)\b", up)
            if m:
                patient = m.group(1)
        if patient is None:
            m = re.search(r"\bPATIENT\s*=\s*([A-Z_]+)\b", up)

        if patient is None:
            m = re.search(r"\bPATIENT\s*=\s*([A-Z_]+)\b", up)

        if patient is None:
            m = re.search(r"\bPATIENT\s*=\s*([A-Z_]+)\b", up)

        # OK: on fait plus simple, on accepte aussi patient=XXX en minuscule
        if patient is None:
            m = re.search(r"\bpatient\s*=\s*([A-Za-z_]+)\b", s)
            if m:
                patient = m.group(1).upper()

        if nurse is None:
            m = re.search(r"\bnurse\s*=\s*([A-Za-z_]+)\b", s)
            if m:
                nurse = m.group(1).upper()
            else:
                m = re.search(r"\binfirmier\s*=\s*([A-Za-z_]+)\b", s)
                if m:
                    nurse = m.group(1).upper()

        return {"patient": patient, "nurse": nurse}
    except Exception:
        return {"patient": None, "nurse": None}


def _summarize_notif_result(raw: str) -> str:
    """Réduit un NotifResult / dict python en résumé lisible (best-effort)."""
    try:
        s = (raw or "").strip()
        if not s:
            return ""
        up = s.upper()

        # On cherche les tokens utiles déjà présents dans tes logs:
        # "PATIENT SMS=SKIPPED EMAIL=SKIPPED; NURSE SMS=SKIPPED EMAIL=SKIPPED"
        m = re.search(r"PATIENT\s+SMS\s*=\s*([A-Z_]+).*?EMAIL\s*=\s*([A-Z_]+)", up)
        p = None
        if m:
            p = f"Patient: SMS={m.group(1)} / Email={m.group(2)}"

        m = re.search(r"NURSE\s+SMS\s*=\s*([A-Z_]+).*?EMAIL\s*=\s*([A-Z_]+)", up)
        n = None
        if m:
            n = f"Infirmier: SMS={m.group(1)} / Email={m.group(2)}"

        parts = [x for x in [p, n] if x]
        return " • ".join(parts) if parts else ""
    except Exception:
        return ""
# ORDO_TIMELINE_HELPERS_V1:END
def _classify_same_status_event(comment: str, current_status: str) -> tuple[str, str, str, str, str]:
    """Retourne (tone, kind, icon, title, subtitle) pour old_status == new_status.

    Objectif UI: éviter 'RECEIVED → RECEIVED' en donnant un libellé premium basé sur le commentaire.
    """
    raw = (comment or "").strip()
    c = _upper(raw)
    status = (current_status or "").strip()

    # ORDO_FR_RULES_V1:BEGIN
    # Règles UI FR premium pour old_status == new_status

    def _split_arrow_payload(payload: str):
        if not payload:
            return None
        p = (payload or "").strip().replace("->", "→").replace("=>", "→")
        if "→" not in p:
            return None
        a, b = p.split("→", 1)
        return a.strip(), b.strip()

    # Commentaire vide => évite 'Opération / IN_PROGRESS' sans sens
    if not raw:
        sub = f"Statut inchangé : {status_fr(status)}" if status else "Statut inchangé"
        return "neutral", "system", "activity", "Mise à jour", sub

    # Origine ordonnance : unknown → speech_therapist (codes -> FR)
    if "ORIGINE" in c and "MODIFI" in c and ":" in raw:
        _label, _payload = raw.split(":", 1)
        pair = _split_arrow_payload(_payload)
        if pair:
            a, b = pair
            return "info", "edit", "shuffle", "Origine ordonnance", f"{origin_fr(a)} → {origin_fr(b)}"

    # Type d’ordonnance : INCOMPLETE → ALD (codes -> FR)
    if ("TYPE" in c) and ("ORDONN" in c) and ("MODIFI" in c) and ":" in raw:
        _label, _payload = raw.split(":", 1)
        pair = _split_arrow_payload(_payload)
        if pair:
            a, b = pair
            return "info", "edit", "shuffle", "Type d’ordonnance", f"{prescription_type_fr(a)} → {prescription_type_fr(b)}"

    # Générique '... modifié : A → B' (fallback premium)
    if ":" in raw and ("MODIFI" in c or "CHANGE" in c or "CHANG" in c):
        label, payload = raw.split(":", 1)
        label = (label or "").strip()
        pair = _split_arrow_payload(payload)
        if pair:
            a, b = pair
            low = label.lower()
            for suf in [" modifié", " modifiée", " modifies", " modified"]:
                if low.endswith(suf):
                    label = label[: -len(suf)].strip()
                    break
            title = label or "Modification"
            return "info", "edit", "shuffle", title, f"{a} → {b}"
    # ORDO_FR_RULES_V1:END

    # Origine ordonnance modifiée
    if "ORIGINE DE L’ORDONNANCE MODIFI" in c or "ORIGINE DE L'ORDONNANCE MODIFI" in c:
        # ex: "Origine de l’ordonnance modifiée : unknown → speech_therapist"
        subtitle = raw.split(":", 1)[-1].strip() if ":" in raw else status
        return "info", "edit", "shuffle", "Origine ordonnance", (subtitle or status)

    # Affectation infirmier
    if "INFIRMIER AFFECT" in c:
        who = raw.split(":", 1)[-1].strip() if ":" in raw else ""
        subtitle = f"Infirmier: {who}" if who else status
        return "info", "assignment", "user-plus", "Affectation infirmier", subtitle

    if "INFIRMIER RETIR" in c or "RETIRER L’INFIRMIER" in c or "RETIRER L'INFIRMIER" in c:
        return "warning", "assignment", "user-x", "Retrait infirmier", "Aucun infirmier affecté"

    # Paramétrage notifications
    if "PARAMÉTRAGE NOTIFICATIONS" in c or "PARAMETRAGE NOTIFICATIONS" in c:
        pch, nch = _parse_notification_settings_comment(raw)
        if pch or nch:
            subtitle = f"Patient: {pch} • Infirmier: {nch}"
        else:
            subtitle = status
        return "info", "notification", "settings", "Paramétrage notifications", subtitle

    # Notification technique (Notif/NotifResult/trigger=...)
    if ("NOTIF" in c) or ("TRIGGER=" in c) or (" TO=" in c) or (" CH=" in c) or (" RES=" in c) or ("NOTIFRESULT" in c):
        summary = _summarize_notif_result(raw)
        return "info", "notification", "bell", "Notification", (summary or status)

    # Message libre
    if "MESSAGE LIBRE" in c:
        return "info", "note", "message-square", "Message libre", status

    return "neutral", "system", "activity", "Opération", status


def build_prescription_timeline_events(prescription) -> List[TimelineEvent]:
    events: List[TimelineEvent] = []

    history_qs = (
        prescription.status_history
        .select_related("changed_by")
        .all()
        .order_by("-changed_at")
    )

    for h in history_qs:
        actor = _safe_username(getattr(h, "changed_by", None))
        old_s = getattr(h, "old_status", "") or ""
        new_s = getattr(h, "new_status", "") or ""

        comment = getattr(h, "comment", None)
        details: List[str] = [str(comment)] if comment else []
        chips = _chips_from_comment(comment or "")

        is_status_change = (old_s != new_s)

        if is_status_change:
            tone, kind, icon = _tone_kind_icon_from_status(new_s)
            title = "Statut modifié"
            subtitle = f"{status_fr(old_s)} → {status_fr(new_s)}".strip(" →")
        else:
            tone, kind, icon, title, subtitle = _classify_same_status_event(comment or "", new_s)



        events.append(
            TimelineEvent(
                uid=f"evt-h-{getattr(h, 'pk', 'x')}",
                ts=getattr(h, "changed_at", None),
                actor_label=actor,
                actor_sub="",
                kind=kind,
                icon=icon,
                tone=tone,
                title=title,
                subtitle=subtitle,
                chips=chips,
                details=details,
                tech=None,
            )
        )

    received_dt = getattr(prescription, "received_at", None) or getattr(prescription, "created_at", None)
    if received_dt:
        events.append(
            TimelineEvent(
                uid=f"evt-received-{getattr(prescription, 'pk', 'x')}",
                ts=received_dt,
                actor_label="Système",
                actor_sub="Gmail",
                kind="system",
                icon="mail",
                tone="info",
                title="Ordonnance reçue",
                subtitle=timezone.localtime(received_dt).strftime("%d/%m/%Y %H:%M"),
                chips=[],
                details=[],
                tech=None,
            )
        )

    now = timezone.now()
    events.sort(key=lambda e: e.ts or now, reverse=True)
    return events
