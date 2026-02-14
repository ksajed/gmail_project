# gmail_manager/core_notifications/services.py
from django.contrib.auth import get_user_model
from .models import Notification
from django.utils import timezone
import re

from datetime import timedelta
from core_notifications.backends.ovh import OvhSmsBackend
from core_notifications.utils_phone import to_e164_fr
from core_notifications.models import SmsMessage, SmsAttempt, SmsStatus, SmsPurpose

User = get_user_model()


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

### ORDO_SMS_LOGGED_HARDENING_V1_START ###
# Guard RGPD: empêcher toute fuite d’infos personnelles/médicales dans les SMS.
_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)

_RGPD_FORBIDDEN_PATTERNS = [
    r"\bnss\b",
    r"\bs[ée]curit[ée]\s+sociale\b",
    r"\bdate\s+de\s+naissance\b",
    r"\bposologie\b",
    r"\bmg\b",
    r"\bml\b",
    r"\bcomprim[ée]s?\b",
    r"\bg[ée]lules?\b",
]

def _assert_sms_rgpd_safe(text: str) -> None:
    t = (text or "").strip()
    if not t:
        raise ValueError("text is required")
    if _EMAIL_RE.search(t):
        raise ValueError("RGPD: SMS text must not contain email addresses.")
    low = t.lower()
    for pat in _RGPD_FORBIDDEN_PATTERNS:
        if re.search(pat, low, flags=re.I):
            raise ValueError("RGPD: SMS text contains forbidden personal/medical markers.")
### ORDO_SMS_LOGGED_HARDENING_V1_END ###

def send_sms_logged(*, to_e164: str, text: str, purpose: str = SmsPurpose.INFO, template_key: str = "", prescription=None) -> SmsMessage:
    """
    Envoie un SMS via OVH et journalise en base (SmsMessage + SmsAttempt).

    Hardening V1:
      - Normalisation FR -> E.164 via to_e164_fr
      - Guard RGPD (pas d’email, pas de marqueurs sensibles)
      - Anti-doublon soft (3 minutes) même destinataire + même texte + même template + même ordonnance
    """
    raw = (to_e164 or "").strip()
    to_norm = to_e164_fr(raw) or (raw if raw.startswith("+") else None)
    if not to_norm:
        raise ValueError("to_e164 is required (E.164 format, e.g. +33...)")

    text = (text or "").strip()
    _assert_sms_rgpd_safe(text)

    # Anti-doublon soft (évite double clic / double transition / retry UI)
    window = timezone.now() - timedelta(minutes=3)
    existing = SmsMessage.objects.filter(
        recipient_phone=to_norm,
        purpose=purpose,
        template_key=template_key,
        rendered_text=text,
        related_prescription=prescription,
        created_at__gte=window,
    ).order_by("-id").first()

    if existing and existing.status in {SmsStatus.QUEUED, SmsStatus.SENT}:
        return existing

    sms = SmsMessage.objects.create(
        recipient_phone=to_norm,
        purpose=purpose,
        template_key=template_key,
        rendered_text=text,
        related_prescription=prescription,
        status=SmsStatus.QUEUED,
    )

    backend = OvhSmsBackend()
    attempt_no = 1

    try:
        res = backend.send(to_norm, text)
        SmsAttempt.objects.create(
            sms_message=sms,
            attempt_no=attempt_no,
            success=True,
            response_payload=res,
        )

        # OVH renvoie souvent {'ids':[...]} (job ids)
        ovh_ids = res.get("ids") if isinstance(res, dict) else None
        if isinstance(ovh_ids, list) and ovh_ids:
            sms.provider_message_id = str(ovh_ids[0])
        else:
            sms.provider_message_id = str(res.get("message_id") or "") if isinstance(res, dict) else ""

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
