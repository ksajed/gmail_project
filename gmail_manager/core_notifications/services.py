# gmail_manager/core_notifications/services.py
from django.contrib.auth import get_user_model
from .models import Notification

from django.utils import timezone
from core_notifications.backends.ovh import OvhSmsBackend
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


def send_sms_logged(*, to_e164: str, text: str, purpose: str = SmsPurpose.INFO, template_key: str = "", prescription=None) -> SmsMessage:
    """
    Envoie un SMS via OVH et journalise en base (SmsMessage + SmsAttempt).
    """
    sms = SmsMessage.objects.create(
        recipient_phone=to_e164,
        purpose=purpose,
        template_key=template_key,
        rendered_text=text,
        related_prescription=prescription,
        status=SmsStatus.QUEUED,
    )

    backend = OvhSmsBackend()
    attempt_no = 1

    try:
        res = backend.send(to_e164, text)
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
