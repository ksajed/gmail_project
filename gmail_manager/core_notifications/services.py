# gmail_manager/core_notifications/services.py
from django.contrib.auth import get_user_model
from django.utils import timezone

from core_notifications.backends.ovh import OvhSmsBackend
from core_notifications.models import SmsMessage, SmsAttempt, SmsStatus, SmsPurpose
import re

_E164_RE = re.compile(r"^\+\d{6,15}$")

def normalize_phone_to_e164_fr(phone: str) -> str:
    """
    Normalise un numéro FR vers E.164.
    - "0748435501" -> "+33748435501"
    - "06 12 34 56 78" -> "+33612345678"
    - "0033..." -> "+33..."
    - "+33..." -> "+33..."
    Retourne "" si impossible.
    """
    raw = (phone or "").strip()
    if not raw:
        return ""
    raw = re.sub(r"[^\d\+]", "", raw)

    if raw.startswith("00"):
        raw = "+" + raw[2:]

    if raw.startswith("+"):
        cand = "+" + re.sub(r"\D", "", raw[1:])
        return cand if _E164_RE.match(cand) else ""

    digits = re.sub(r"\D", "", raw)
    if not digits:
        return ""

    if digits.startswith("0") and len(digits) == 10:
        cand = "+33" + digits[1:]
        return cand if _E164_RE.match(cand) else ""

    if len(digits) == 9:
        cand = "+33" + digits
        return cand if _E164_RE.match(cand) else ""

    if digits.startswith("33") and len(digits) == 11:
        cand = "+33" + digits[2:]
        return cand if _E164_RE.match(cand) else ""

    return ""


from .models import Notification

User = get_user_model()


# PHONE_E164_NORMALIZE:BEGIN
import re as _re

def normalize_phone_e164(raw: str) -> str:
    """
    Normalise un numéro en E.164 (focus FR).
    Ex:
      - "0748435501" -> "+33748435501"
      - "06 12 34 56 78" -> "+33612345678"
      - "+33 6 12 34 56 78" -> "+33612345678"
      - "00336..." -> "+336..."
    Retourne "" si invalide/indéterminable.
    """
    s = (raw or "").strip()
    if not s:
        return ""

    # Retire séparateurs usuels
    s = s.replace(" ", "").replace(".", "").replace("-", "").replace("(", "").replace(")", "")

    # 00XX -> +XX
    if s.startswith("00"):
        s = "+" + s[2:]

    # Cas déjà en +...
    if s.startswith("+"):
        digits = _re.sub(r"\D", "", s)  # garde uniquement chiffres après +
        if not digits:
            return ""

        # Cas +33(0)6... => enlever le 0 parasite
        if digits.startswith("33") and len(digits) >= 3 and digits[2] == "0":
            # +3306XXXXXXXX => +336XXXXXXXX
            digits = "33" + digits[3:]

        return "+" + digits

    # Sinon digits only
    digits = _re.sub(r"\D", "", s)
    if not digits:
        return ""

    # "33" + 9 digits
    if digits.startswith("33") and len(digits) == 11:
        return "+" + digits

    # FR national 10 digits "0XXXXXXXXX"
    if len(digits) == 10 and digits.startswith("0"):
        return "+33" + digits[1:]

    # Parfois stocké sans 0 (9 digits) — on accepte en FR
    if len(digits) == 9:
        return "+33" + digits

    return ""
# PHONE_E164_NORMALIZE:END

def notify_users(*, users, title, message, object_type="", object_id=None):
    """
    Crée une notification pour une liste d'utilisateurs.

    - users : QuerySet ou liste d'utilisateurs
    - title : titre court
    - message : message détaillé
    - object_type / object_id : lien métier optionnel
    """

    notifications = []

    for user in users:
        notifications.append(
            Notification(
                recipient=user,
                title=title,
                message=message,
                object_type=object_type,
                object_id=object_id,
            )
        )

    Notification.objects.bulk_create(notifications)

#====================================================================================
# OVH SMS SENDING SERVICE
#====================================================================================
def send_sms_logged(*, to_e164: str, text: str, purpose: str = SmsPurpose.INFO, template_key: str = "", prescription=None) -> SmsMessage:
    """
    Envoie un SMS via OVH et journalise en base (SmsMessage + SmsAttempt).

    - Normalise automatiquement les numéros FR vers E.164 (+33...)
    - Si numéro invalide => SmsMessage + SmsAttempt en FAILED (sans appel OVH)
    """
    raw_input = (to_e164 or "").strip()
    normalized = normalize_phone_to_e164_fr(raw_input)
    recipient = normalized or raw_input

    sms = SmsMessage.objects.create(
        recipient_phone=recipient,
        purpose=purpose,
        template_key=template_key,
        rendered_text=text,
        related_prescription=prescription,
        status=SmsStatus.QUEUED,
    )

    attempt_no = 1

    if not normalized or not _E164_RE.match(normalized):
        err = f"Numéro invalide (E.164 attendu). Reçu: {raw_input}"
        SmsAttempt.objects.create(
            sms_message=sms,
            attempt_no=attempt_no,
            success=False,
            error_message=err,
        )
        sms.status = SmsStatus.FAILED
        sms.last_error_message = err
        sms.save(update_fields=["status", "last_error_message"])
        return sms

    backend = OvhSmsBackend()

    try:
        res = backend.send(normalized, text)
        SmsAttempt.objects.create(
            sms_message=sms,
            attempt_no=attempt_no,
            success=True,
            response_payload=res.get("raw"),
        )
        sms.provider_message_id = res.get("message_id") or ""
        sms.status = SmsStatus.SENT
        sms.sent_at = timezone.now()
        sms.last_error_message = ""
        sms.save(update_fields=["provider_message_id", "status", "sent_at", "last_error_message"])
        return sms

    except Exception as e:
        SmsAttempt.objects.create(
            sms_message=sms,
            attempt_no=attempt_no,
            success=False,
            error_message=str(e),
        )
        sms.status = SmsStatus.FAILED
        sms.last_error_message = str(e)
        sms.save(update_fields=["status", "last_error_message"])
        return sms
