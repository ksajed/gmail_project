from core_notifications.pharmacy_identity import (
    PHARMACY_SIGNATURE_FR_SMS_COMPACT,
    PHARMACY_SIGNATURE_EN_SMS_COMPACT,
)

# Mapping minimal FR -> EN (adapter si tes labels diffèrent)
STATUS_EN = {
    "Réception OK": "Received",
    "Rejetée": "Rejected",
    "En cours de traitement": "In processing",
    "En attente de livraison": "Awaiting delivery",
    "Livrée": "Delivered",
}

def status_fr_to_en(label_fr: str) -> str:
    return STATUS_EN.get(label_fr, label_fr)

def render_status_sms_rgpd_bilingual_compact(status_label_fr: str, prescription_id: int | None = None) -> str:
    """RGPD: no patient name, no medical info, ONLY status + reference + pharmacy identity.
    FR first, EN below. Short to reduce multi-SMS.
    """
    status_label_en = status_fr_to_en(status_label_fr)

    ref_fr = f" Réf: {prescription_id}." if prescription_id is not None else ""
    ref_en = f" Ref: {prescription_id}." if prescription_id is not None else ""

    fr = f"Bonjour. Statut ordonnance : {status_label_fr}.{ref_fr} Merci. {PHARMACY_SIGNATURE_FR_SMS_COMPACT}"
    en = f"EN: Hello. Prescription status: {status_label_en}.{ref_en} Thank you. {PHARMACY_SIGNATURE_EN_SMS_COMPACT}"
    return fr + "\n" + en

### ORDO_STATUS_SMS_MAP_V1_START ###
# -*- coding: utf-8 -*-
from typing import Tuple

PHARMACY_NAME_FALLBACK = "La Grande Pharmacie de Fives"
PHARMACY_PHONE_FALLBACK = "03 20 56 50 05"

def _get_pharmacy_identity() -> tuple[str, str]:
    try:
        from core_notifications.pharmacy_identity import PHARMACY_NAME, PHARMACY_PHONE  # type: ignore
        name = (PHARMACY_NAME or "").strip() or PHARMACY_NAME_FALLBACK
        phone = (PHARMACY_PHONE or "").strip() or PHARMACY_PHONE_FALLBACK
        return name, phone
    except Exception:
        return PHARMACY_NAME_FALLBACK, PHARMACY_PHONE_FALLBACK

def _sig() -> str:
    name, phone = _get_pharmacy_identity()
    return "\n\n" + name + "\n📞 " + phone

STATUS_HUMAN = {
    "RECEIVED":    "Reçue par la pharmacie",
    "IN_PROGRESS": "En cours de préparation",
    "READY":       "Prête",
    "DELIVERED":   "Délivrée",
    "BLOCKED":     "En attente de traitement",
    "REJECTED":    "Non traitable en l’état",
    "ARCHIVED":    "Dossier clôturé",
}

def _patient_template(status_human: str) -> str:
    return (
        "Bonjour,\n\n"
        "Le statut de votre ordonnance a évolué.\n"
        "État actuel : " + status_human + "."
        + _sig()
    )

def _nurse_template(status_human: str) -> str:
    return (
        "Bonjour,\n\n"
        "Le statut d’une ordonnance associée à votre patient a évolué.\n"
        "État actuel : " + status_human + "."
        + _sig()
    )

def get_sms_texts_for_status(status: str) -> Tuple[str, str]:
    s = (status or "").strip().upper()
    human = STATUS_HUMAN.get(s, "Mise à jour en cours")
    return _patient_template(human), _nurse_template(human)

STATUS_SMS_MAP = {
    k: {"patient_sms": get_sms_texts_for_status(k)[0], "nurse_sms": get_sms_texts_for_status(k)[1]}
    for k in STATUS_HUMAN.keys()
}
### ORDO_STATUS_SMS_MAP_V1_END ###
