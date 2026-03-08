# gmail_manager/core_emails/states.py
from enum import Enum


class PrescriptionStatusEnum(str, Enum):
    RECEIVED = "RECEIVED"         # Ordonnance reçue
    IN_PROGRESS = "IN_PROGRESS"   # En cours de préparation
    READY = "READY"               # Prête à être délivrée
    DELIVERED = "DELIVERED"       # Délivrée
    REJECTED = "REJECTED"         # Refusée
    BLOCKED = "BLOCKED"           # Legacy / compatibilité historique
    ARCHIVED = "ARCHIVED"         # Clôture administrative


STATUS_LABELS_FR = {
    PrescriptionStatusEnum.RECEIVED: "Reçue",
    PrescriptionStatusEnum.IN_PROGRESS: "En cours",
    PrescriptionStatusEnum.READY: "Prête",
    PrescriptionStatusEnum.DELIVERED: "Délivrée",
    PrescriptionStatusEnum.REJECTED: "Refusée",
    PrescriptionStatusEnum.BLOCKED: "Bloquée",
    PrescriptionStatusEnum.ARCHIVED: "Archivée",
}


def get_status_label_fr(status):
    try:
        enum_value = status if isinstance(status, PrescriptionStatusEnum) else PrescriptionStatusEnum(status)
        return STATUS_LABELS_FR.get(enum_value, getattr(enum_value, "value", str(status)))
    except Exception:
        if status == "REJECTED":
            return "Refusée"
        if status == "BLOCKED":
            return "Bloquée"
        return str(status or "—")


# 🔒 TABLE OFFICIELLE DES TRANSITIONS AUTORISÉES (SOURCE UNIQUE)
PRESCRIPTION_STATUS_TRANSITIONS = {
    PrescriptionStatusEnum.RECEIVED: {
        PrescriptionStatusEnum.IN_PROGRESS,
        PrescriptionStatusEnum.REJECTED,
    },
    PrescriptionStatusEnum.IN_PROGRESS: {
        PrescriptionStatusEnum.READY,
        PrescriptionStatusEnum.REJECTED,
    },
    PrescriptionStatusEnum.READY: {
        PrescriptionStatusEnum.DELIVERED,
    },
    PrescriptionStatusEnum.DELIVERED: {
        PrescriptionStatusEnum.ARCHIVED,
    },
    PrescriptionStatusEnum.REJECTED: {
        PrescriptionStatusEnum.ARCHIVED,
    },
    PrescriptionStatusEnum.BLOCKED: {
        PrescriptionStatusEnum.ARCHIVED,
    },
    PrescriptionStatusEnum.ARCHIVED: set(),
}
