from __future__ import annotations

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
