# gmail_manager/core_emails/states.py
from enum import Enum


class PrescriptionStatusEnum(str, Enum):
    RECEIVED = "RECEIVED"        # Ordonnance reçue
    IN_PROGRESS = "IN_PROGRESS" # En cours de préparation
    READY = "READY"              # Prête à être délivrée
    DELIVERED = "DELIVERED"      # Délivrée
    BLOCKED = "BLOCKED"          # Problème (illisible, rupture, etc.)
    ARCHIVED = "ARCHIVED"        # Clôture administrative


# 🔒 TABLE OFFICIELLE DES TRANSITIONS AUTORISÉES (SOURCE UNIQUE)
PRESCRIPTION_STATUS_TRANSITIONS = {
    PrescriptionStatusEnum.RECEIVED: {
        PrescriptionStatusEnum.IN_PROGRESS,
        PrescriptionStatusEnum.BLOCKED,
    },
    PrescriptionStatusEnum.IN_PROGRESS: {
        PrescriptionStatusEnum.READY,
        PrescriptionStatusEnum.BLOCKED,
    },
    PrescriptionStatusEnum.READY: {
        PrescriptionStatusEnum.DELIVERED,
        PrescriptionStatusEnum.BLOCKED,  # blocage tardif justifié
    },
    PrescriptionStatusEnum.DELIVERED: {
        PrescriptionStatusEnum.ARCHIVED,
    },
    PrescriptionStatusEnum.BLOCKED: {
        PrescriptionStatusEnum.ARCHIVED,
    },
    PrescriptionStatusEnum.ARCHIVED: set(),  # ⛔ état final
}
