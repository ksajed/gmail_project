# gmail_manager/core_gmail/services.py

import imaplib
import email
from email.header import decode_header
from datetime import datetime
import time
import re

from django.conf import settings
from django.utils import timezone
from django.core.files.base import ContentFile

from core_gmail.models import GmailMessage
from core_emails.models import (
    Prescription,
    PrescriptionStatus,
    PrescriptionType,  # ✅ IMPORTANT
)
from core_attachments.models import PrescriptionAttachment

# ✅ GESTION PATIENT
from core_patients.services import get_or_create_patient_from_email


def _default_search_criteria():
    """
    Stratégie Gmail robuste:
    - UNSEEN sur Gmail est souvent vide (mails déjà "vus" par un client)
    - On préfère récupérer une fenêtre récente (anti-doublon Message-ID)
    """
    crit = getattr(settings, "GMAIL_IMAP_SEARCH", None)
    if crit:
        return crit
    # Gmail extension IMAP (supportée par Gmail)
    return ("X-GM-RAW", "newer_than:30d")


def _build_search_args(search_criteria):
    """
    Retourne une liste d'arguments à passer à mail.search(None, *args)

    Supporte:
    - "UNSEEN"
    - ("X-GM-RAW", "newer_than:30d")
    - "X-GM-RAW newer_than:30d"
    - "X-GM-RAW:newer_than:30d"
    """
    if isinstance(search_criteria, (tuple, list)):
        return [str(x) for x in search_criteria]

    crit = (search_criteria or "").strip()
    if not crit:
        return ["UNSEEN"]

    up = crit.upper()

    # Format: X-GM-RAW:<query>
    if up.startswith("X-GM-RAW:"):
        query = crit.split(":", 1)[1].strip()
        query = query.strip("'").strip('"')
        return ["X-GM-RAW", query]

    # Format: X-GM-RAW <query>
    if up.startswith("X-GM-RAW"):
        parts = crit.split(None, 1)
        if len(parts) == 1:
            return ["X-GM-RAW", "newer_than:30d"]
        query = parts[1].strip().strip("'").strip('"')
        return ["X-GM-RAW", query]

    return [crit]


def fetch_new_gmail_messages(search_criteria=None, limit=None):
    """
    Robuste:
    - Support criteria string OU list/tuple (ex: ["X-GM-RAW","newer_than:7d"])
    - Anti-doublon:
        Message-ID si présent
        sinon fallback X-GM-MSGID
        sinon fallback UID
    - Statistiques détaillées
    """
    t0 = time.monotonic()

    stats = {
        "search_criteria": search_criteria,
        "candidates": 0,
        "skipped_existing": 0,
        "created_messages": 0,
        "created_prescriptions": 0,
        "saved_attachments": 0,
        "missing_message_id": 0,
        "errors": 0,
        "duration_s": 0.0,
    }

    # default: fenêtre récente (évite rater "Seen")
    if search_criteria is None:
        search_criteria = ["X-GM-RAW", "newer_than:7d"]

    # Normaliser critères
    if isinstance(search_criteria, (list, tuple)):
        criteria_args = [str(x) for x in search_criteria]
    else:
        criteria_args = [str(search_criteria)]

    stats["search_criteria"] = criteria_args

    UID_RE = re.compile(rb"\bUID\s+(\d+)\b")
    GMMSGID_RE = re.compile(rb"\bX-GM-MSGID\s+(\d+)\b")

    mail = imaplib.IMAP4_SSL(settings.GMAIL_IMAP_HOST, settings.GMAIL_IMAP_PORT)

    try:
        mail.login(settings.GMAIL_EMAIL, settings.GMAIL_APP_PASSWORD)
        mail.select("INBOX")

        status, messages_ = mail.search(None, *criteria_args)
        if status != "OK":
            return stats

        nums = messages_[0].split() if messages_ and messages_[0] else []
        stats["candidates"] = len(nums)

        if limit:
            nums = nums[: int(limit)]

        for num in nums:
            try:
                # Fetch meta + headers en 1 fois
                status, hdr_data = mail.fetch(
                    num,
                    "(UID X-GM-MSGID BODY.PEEK[HEADER.FIELDS (MESSAGE-ID SUBJECT FROM DATE)])"
                )
                if status != "OK" or not hdr_data or not hdr_data[0]:
                    continue

                meta = hdr_data[0][0] or b""
                hdr_bytes = hdr_data[0][1] if len(hdr_data[0]) > 1 else b""
                if not hdr_bytes:
                    continue

                uid = None
                gm_msgid = None
                m_uid = UID_RE.search(meta)
                if m_uid:
                    uid = m_uid.group(1).decode("ascii", errors="ignore")
                m_gm = GMMSGID_RE.search(meta)
                if m_gm:
                    gm_msgid = m_gm.group(1).decode("ascii", errors="ignore")

                hdr_msg = email.message_from_bytes(hdr_bytes)

                message_id = (hdr_msg.get("Message-ID") or "").strip()

                # fallback dedupe
                if not message_id:
                    stats["missing_message_id"] += 1
                    if gm_msgid:
                        message_id = f"gm:{gm_msgid}"
                    elif uid:
                        message_id = f"uid:{uid}"
                    else:
                        # dernier fallback: num
                        message_id = f"num:{num.decode('ascii', errors='ignore')}"

                if GmailMessage.objects.filter(message_id=message_id).exists():
                    stats["skipped_existing"] += 1
                    continue

                # Fetch complet RFC822 seulement si nouveau
                status, full_data = mail.fetch(num, "(RFC822)")
                if status != "OK" or not full_data or not full_data[0] or not full_data[0][1]:
                    continue

                msg = email.message_from_bytes(full_data[0][1])

                # Subject / From / received_at via headers
                subject_raw = hdr_msg.get("Subject") or ""
                subject, encoding = decode_header(subject_raw)[0] if subject_raw else ("", None)
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding or "utf-8", errors="ignore")

                from_email = email.utils.parseaddr(hdr_msg.get("From"))[1]

                date_tuple = email.utils.parsedate_tz(hdr_msg.get("Date"))
                received_at = (
                    datetime.fromtimestamp(
                        email.utils.mktime_tz(date_tuple),
                        tz=timezone.get_current_timezone()
                    )
                    if date_tuple
                    else timezone.now()
                )

                # Patient
                patient = get_or_create_patient_from_email(from_email)

                # Créer GmailMessage
                gmail_message = GmailMessage.objects.create(
                    message_id=message_id,
                    subject=subject or "",
                    from_email=from_email,
                    received_at=received_at,
                )
                stats["created_messages"] += 1

                # Prescription
                prescription = Prescription.objects.create(
                    patient=patient,
                    status=PrescriptionStatus.RECEIVED,
                    type=PrescriptionType.INCOMPLETE,
                )
                stats["created_prescriptions"] += 1

                # Pièces jointes
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
                        attachment.file.save(filename, ContentFile(payload), save=True)
                        stats["saved_attachments"] += 1

                # Marquer lu uniquement après succès
                mail.store(num, "+FLAGS", "\\Seen")

            except Exception:
                stats["errors"] += 1
                # continue pour ne pas bloquer toute la sync
                continue

    finally:
        try:
            mail.logout()
        except Exception:
            pass
        stats["duration_s"] = round(time.monotonic() - t0, 2)

    return stats

