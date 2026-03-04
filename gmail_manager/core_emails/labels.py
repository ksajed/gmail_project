# core_emails/labels.py

# ORDO_LABELS:BEGIN
# Traductions métier centralisées (UI 100% FR).
# Les codes techniques restent en DB, l'UI affiche des libellés FR.

STATUS_LABELS = {
    "RECEIVED": "Reçue",
    "IN_PROGRESS": "En cours",
    "READY": "Prête",
    "DELIVERED": "Livrée",
    "REJECTED": "Rejetée",
    "BLOCKED": "Bloquée",
    "ARCHIVED": "Archivée",
    # types éventuels
    "INCOMPLETE": "Incomplète",
}

ORIGIN_LABELS = {
    "unknown": "Inconnue",
    "doctor": "Médecin",
    "speech_therapist": "Orthophoniste",
    "nurse": "Infirmier",
    "hospital": "Hôpital",
    "pharmacy": "Pharmacie",
}

PRESCRIPTION_TYPE_LABELS = {
    "INCOMPLETE": "Incomplète",
    "ALD": "ALD",
    "CLASSIC": "Ordinaire",
}

def status_fr(value: str) -> str:
    return STATUS_LABELS.get((value or "").upper(), value or "—")

def origin_fr(value: str) -> str:
    return ORIGIN_LABELS.get((value or "").lower(), value or "—")

def prescription_type_fr(value: str) -> str:
    return PRESCRIPTION_TYPE_LABELS.get((value or "").upper(), value or "—")
# ORDO_LABELS:END

