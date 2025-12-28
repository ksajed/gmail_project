# gmail_manager/core_gmail/services.py
import imaplib
import email
from email.header import decode_header
from datetime import datetime

from django.conf import settings
from django.utils import timezone
from django.core.files.base import ContentFile

from core_gmail.models import GmailMessage
from core_emails.models import Prescription, PrescriptionStatus
from core_attachments.models import PrescriptionAttachment

# ✅ GESTION PATIENT
from core_patients.services import get_or_create_patient_from_email


def fetch_new_gmail_messages():
    """
    Récupère les emails Gmail et crée :
    - Patient (si inexistant)
    - Prescription liée au patient
    - Pièces jointes
    - GmailMessage (anti-doublon robuste)
    """

    # ============================================================
    # CONNEXION IMAP
    # ============================================================

    mail = imaplib.IMAP4_SSL(
        settings.GMAIL_IMAP_HOST,
        settings.GMAIL_IMAP_PORT
    )
    mail.login(
        settings.GMAIL_EMAIL,
        settings.GMAIL_APP_PASSWORD
    )

    mail.select("inbox")

    status, messages = mail.search(None, "ALL")
    if status != "OK":
        mail.logout()
        return

    for num in messages[0].split():
        status, data = mail.fetch(num, "(RFC822)")
        if status != "OK":
            continue

        msg = email.message_from_bytes(data[0][1])

        message_id = msg.get("Message-ID")
        if not message_id:
            continue

        # ========================================================
        # MÉTADONNÉES EMAIL (AVANT TRAITEMENT)
        # ========================================================

        subject, encoding = decode_header(msg.get("Subject"))[0]
        if isinstance(subject, bytes):
            subject = subject.decode(
                encoding or "utf-8",
                errors="ignore"
            )

        from_email = email.utils.parseaddr(msg.get("From"))[1]

        date_tuple = email.utils.parsedate_tz(msg.get("Date"))
        received_at = datetime.fromtimestamp(
            email.utils.mktime_tz(date_tuple),
            tz=timezone.get_current_timezone()
        )

        # ========================================================
        # 🔐 ANTI-DOUBLON ROBUSTE
        # ========================================================

        gmail_message, created = GmailMessage.objects.get_or_create(
            message_id=message_id,
            defaults={
                "subject": subject or "",
                "from_email": from_email,
                "received_at": received_at,
            }
        )

        if not created:
            # Email déjà traité
            continue

        # ========================================================
        # 🧍 PATIENT
        # ========================================================

        patient = get_or_create_patient_from_email(from_email)

        # ========================================================
        # 📄 ORDONNANCE
        # ========================================================

        prescription = Prescription.objects.create(
            patient=patient,
            status=PrescriptionStatus.RECEIVED
        )

        # ========================================================
        # 📎 PIÈCES JOINTES
        # ========================================================

        for part in msg.walk():
            if part.get_content_disposition() == "attachment":
                filename = part.get_filename()
                if not filename:
                    continue

                payload = part.get_payload(decode=True)
                if not payload:
                    continue

                attachment = PrescriptionAttachment.objects.create(
                    prescription=prescription,
                    original_filename=filename,
                    mime_type=part.get_content_type(),
                )

                attachment.file.save(
                    filename,
                    ContentFile(payload),
                    save=True
                )

        # Marquer comme LU sur Gmail
        mail.store(num, "+FLAGS", "\\Seen")

    mail.logout()
