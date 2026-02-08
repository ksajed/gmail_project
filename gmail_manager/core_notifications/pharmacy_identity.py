from __future__ import annotations

# Identité officielle pharmacie (Ordo)
PHARMACY_NAME = "La Grande Pharmacie de Fives - Lille"
PHARMACY_ADDRESS_LINE1 = "132 Rue Pierre Legrand"
PHARMACY_ADDRESS_LINE2 = "59800 Lille"
PHARMACY_PHONE = "03 20 56 50 05"

# Signatures SMS compactes (anti multi-SMS)
PHARMACY_SIGNATURE_FR_SMS_COMPACT = (
    f"{PHARMACY_NAME}, {PHARMACY_ADDRESS_LINE1}, {PHARMACY_ADDRESS_LINE2}. "
    f"Tél : {PHARMACY_PHONE}"
)

PHARMACY_SIGNATURE_EN_SMS_COMPACT = (
    f"{PHARMACY_NAME}, {PHARMACY_ADDRESS_LINE1}, {PHARMACY_ADDRESS_LINE2}. "
    f"Phone: {PHARMACY_PHONE}"
)

# Signatures email (si utile plus tard)
PHARMACY_SIGNATURE_FR_EMAIL = (
    "—\n"
    f"{PHARMACY_NAME}\n"
    f"{PHARMACY_ADDRESS_LINE1}\n"
    f"{PHARMACY_ADDRESS_LINE2}\n"
    f"Téléphone : {PHARMACY_PHONE}"
)

PHARMACY_SIGNATURE_EN_EMAIL = (
    "—\n"
    f"{PHARMACY_NAME}\n"
    f"{PHARMACY_ADDRESS_LINE1}\n"
    f"{PHARMACY_ADDRESS_LINE2}\n"
    f"Phone: {PHARMACY_PHONE}"
)
