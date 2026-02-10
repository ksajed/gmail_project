# -*- coding: utf-8 -*-
"""core_emails.services_notifications

Centralisation des notifications (patient / infirmier) déclenchées lors des événements métier.
- Policy NONE/SMS/EMAIL/BOTH
- SMS RGPD: aucune info médicale / pas de nom patient
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from django.core.mail import send_mail

def _send_email_if_possible(*, to_email: str, subject: str, body: str) -> str:
    """Compat: ancien helper email. Délègue vers _send_email_strict()."""
    return _send_email_strict(to_email=to_email, subject=subject, body=body)

from core_notifications.models import SmsPurpose
from core_notifications.services import send_sms_logged


NotificationChannel = Literal["NONE", "SMS", "EMAIL", "BOTH"]


@dataclass(frozen=True)
class NotificationPlan:
    patient_channel: NotificationChannel = "NONE"
    nurse_channel: NotificationChannel = "NONE"


def _status_label_fr(status: str) -> str:
    try:
        from core_emails.models import PrescriptionStatus
        return dict(PrescriptionStatus.choices).get(status, status or "—")
    except Exception:
        return status or "—"


def build_sms_text_status_only(*, prescription, old_status: str, new_status: str) -> str:
    """SMS RGPD-safe: statut uniquement."""
    # IMPORTANT: pas de nom patient, pas d'ordonnance détaillée, pas de pathologie.
    return (
        "[Ordo] Mise à jour: statut de votre ordonnance : "
        f"{_status_label_fr(old_status)} → {_status_label_fr(new_status)}."
    )


def _send_email_strict(*, to_email: str, subject: str, body: str) -> None:
    to_email = (to_email or "").strip()
    if not to_email:
        return
    send_mail(
        subject=subject,
        message=body,
        from_email=None,
        recipient_list=[to_email],
        fail_silently=True,
    )


def notify_patient(
    *,
    prescription,
    old_status: str,
    new_status: str,
    channel: NotificationChannel,
    patient_phone: Optional[str],
    patient_email: Optional[str],
) -> None:
    if channel == "NONE":
        return

    sms_text = build_sms_text_status_only(prescription=prescription, old_status=old_status, new_status=new_status)

    if channel in ("SMS", "BOTH"):
        if patient_phone:
            send_sms_logged(
                to_e164=patient_phone,
                text=sms_text,
                purpose=SmsPurpose.INFO,
                template_key="status_update_patient",
                prescription=prescription,
            )

    if channel in ("EMAIL", "BOTH"):
        if patient_email:
            _send_email_strict(
                to_email=patient_email,
                subject="Mise à jour du statut de votre ordonnance",
                body=sms_text,
            )


def notify_nurse(
    *,
    prescription,
    old_status: str,
    new_status: str,
    channel: NotificationChannel,
    nurse_phone: Optional[str],
    nurse_email: Optional[str],
) -> None:
    if channel == "NONE":
        return

    # RGPD: côté infirmier aussi, rester au statut uniquement (tu peux ajuster plus tard)
    sms_text = (
        "[Ordo] Mise à jour: statut ordonnance (patient) : "
        f"{_status_label_fr(old_status)} → {_status_label_fr(new_status)}."
    )

    if channel in ("SMS", "BOTH"):
        if nurse_phone:
            send_sms_logged(
                to_e164=nurse_phone,
                text=sms_text,
                purpose=SmsPurpose.INFO,
                template_key="status_update_nurse",
                prescription=prescription,
            )

    if channel in ("EMAIL", "BOTH"):
        if nurse_email:
            _send_email_if_possible(
                to_email=nurse_email,
                subject="Mise à jour du statut d'une ordonnance",
                body=sms_text,
            )


def send_prescription_notifications(
    *,
    prescription,
    old_status: str,
    new_status: str,
    patient_channel: NotificationChannel,
    nurse_channel: NotificationChannel,
) -> None:
    """Point d’entrée unique côté notifications métier.

    NB: Exécution recommandée AFTER COMMIT (déjà fait dans services_workflow).
    """

    # Patient contacts
    patient = getattr(prescription, "patient", None)
    patient_phone = getattr(patient, "phone_number", None) if patient else None
    patient_email = getattr(patient, "email", None) if patient else None

    notify_patient(
        prescription=prescription,
        old_status=old_status,
        new_status=new_status,
        channel=patient_channel,
        patient_phone=patient_phone,
        patient_email=patient_email,
    )

    # Nurse contacts (si associé)
    nurse = getattr(prescription, "assigned_nurse", None)
    if nurse:
        nurse_phone = getattr(nurse, "phone_number", None) or getattr(nurse, "phone", None)
        nurse_email = getattr(nurse, "email", None)
        notify_nurse(
            prescription=prescription,
            old_status=old_status,
            new_status=new_status,
            channel=nurse_channel,
            nurse_phone=nurse_phone,
            nurse_email=nurse_email,
        )


def mask_phone(phone: str) -> str:
    phone = (phone or "").strip()
    if not phone:
        return "—"
    # On masque tout sauf préfixe + 3 derniers chiffres
    keep_last = phone[-3:] if len(phone) >= 3 else phone
    if phone.startswith("+33"):
        return "+33******" + keep_last
    if phone.startswith("+"):
        return phone[:3] + "******" + keep_last
    return "******" + keep_last


def mask_email(email: str) -> str:
    email = (email or "").strip()
    if not email or "@" not in email:
        return "—"
    name, domain = email.split("@", 1)
    if not name:
        return "***@" + domain
    return (name[0] + "***@" + domain)


def build_notification_audit_summary(
    *,
    prescription,
    patient_channel: str,
    nurse_channel: str,
    patient_phone: str | None,
    patient_email: str | None,
    nurse_phone: str | None,
    nurse_email: str | None,
) -> str:
    """Résumé RGPD-safe à mettre dans l'historique métier.

    Ne contient ni nom patient ni info médicale.
    """
    def fmt_target(channel: str, phone: str | None, email: str | None) -> str:
        channel = (channel or "NONE").upper()
        if channel == "NONE":
            return "NONE"
        if channel == "SMS":
            return f"SMS({mask_phone(phone or '')})"
        if channel == "EMAIL":
            return f"EMAIL({mask_email(email or '')})"
        if channel == "BOTH":
            return f"BOTH({mask_phone(phone or '')}, {mask_email(email or '')})"
        return channel

    patient_part = fmt_target(patient_channel, patient_phone, patient_email)
    nurse_part = fmt_target(nurse_channel, nurse_phone, nurse_email)

    # Si pas d'infirmier associé, on log "NURSE=NO_ASSOC"
    nurse_obj = getattr(prescription, "assigned_nurse", None)
    if not nurse_obj:
        nurse_part = "NO_ASSOC"

    return f"Notif: PATIENT={patient_part} ; NURSE={nurse_part}"


def build_notification_result_summary(
    *,
    prescription,
    patient_channel: str,
    nurse_channel: str,
    patient_phone: str | None,
    patient_email: str | None,
    nurse_phone: str | None,
    nurse_email: str | None,
    patient_sms_status: str,
    patient_email_status: str,
    nurse_sms_status: str,
    nurse_email_status: str,
) -> str:
    """Résumé RGPD-safe du résultat réel (after commit).

    Exemples:
      NotifResult: PATIENT=SMS(SENT) ; NURSE=NO_ASSOC
      NotifResult: PATIENT=BOTH(SMS=SENT, EMAIL=FAILED) ; NURSE=SMS(SENT)
    """
    def fmt(channel: str, sms_status: str, email_status: str) -> str:
        c = (channel or "NONE").upper()
        if c == "NONE":
            return "NONE(SKIPPED)"
        if c == "SMS":
            return f"SMS({sms_status})"
        if c == "EMAIL":
            return f"EMAIL({email_status})"
        if c == "BOTH":
            return f"BOTH(SMS={sms_status}, EMAIL={email_status})"
        return c

    patient_part = fmt(patient_channel, patient_sms_status, patient_email_status)

    nurse_obj = getattr(prescription, "assigned_nurse", None)
    if not nurse_obj:
        nurse_part = "NO_ASSOC"
    else:
        nurse_part = fmt(nurse_channel, nurse_sms_status, nurse_email_status)

    return f"NotifResult: PATIENT={patient_part} ; NURSE={nurse_part}"


def _send_email_strict(*, to_email: str, subject: str, body: str) -> str:
    """Envoi email avec résultat réel (SENT/FAILED/SKIPPED)."""
    to_email = (to_email or "").strip()
    if not to_email:
        return "SKIPPED"
    try:
        # send_mail renvoie un int (nb emails envoyés). 1 => OK
        n = send_mail(
            subject=subject,
            message=body,
            from_email=None,
            recipient_list=[to_email],
            fail_silently=False,
        )
        return "SENT" if n else "FAILED"
    except Exception:
        return "FAILED"


# =========================
# NotifResult v1 (override safe)
# =========================

def build_notification_result_summary(
    *,
    prescription,
    patient_channel: str,
    nurse_channel: str,
    patient_sms_status: str,
    patient_email_status: str,
    nurse_sms_status: str,
    nurse_email_status: str,
) -> str:
    def fmt(channel: str, sms_status: str, email_status: str) -> str:
        c = (channel or "NONE").upper()
        if c == "NONE":
            return "NONE(SKIPPED)"
        if c == "SMS":
            return f"SMS({sms_status})"
        if c == "EMAIL":
            return f"EMAIL({email_status})"
        if c == "BOTH":
            return f"BOTH(SMS={sms_status}, EMAIL={email_status})"
        return c

    patient_part = fmt(patient_channel, patient_sms_status, patient_email_status)

    nurse_obj = getattr(prescription, "assigned_nurse", None)
    if not nurse_obj:
        nurse_part = "NO_ASSOC"
    else:
        nurse_part = fmt(nurse_channel, nurse_sms_status, nurse_email_status)

    return f"NotifResult: PATIENT={patient_part} ; NURSE={nurse_part}"


def _email_status_from_helper(ret) -> str:
    # ton compat _send_email_if_possible peut renvoyer str ("SENT/FAILED/SKIPPED") ou None
    if isinstance(ret, str) and ret.strip():
        return ret.strip().upper()
    # si helper best-effort (None), on considère SENT au mieux
    return "SENT"


def send_prescription_notifications(
    *,
    prescription,
    old_status=None,
    new_status=None,
    patient_channel="NONE",
    nurse_channel="NONE",
):
    """Override SAFE : envoi réel + retour NotifResult (RGPD-safe).

    Cette définition en fin de fichier écrase l'ancienne sans risque d'insertion.
    """
    old_status = old_status if old_status is not None else getattr(prescription, "status", "")
    new_status = new_status if new_status is not None else getattr(prescription, "status", "")

    patient = getattr(prescription, "patient", None)
    patient_phone = getattr(patient, "phone_number", None) if patient else None
    patient_email = getattr(patient, "email", None) if patient else None

    nurse = getattr(prescription, "assigned_nurse", None)
    nurse_phone = None
    nurse_email = None
    if nurse:
        nurse_phone = getattr(nurse, "phone_number", None) or getattr(nurse, "phone", None)
        nurse_email = getattr(nurse, "email", None)

    patient_sms_status = "SKIPPED"
    patient_email_status = "SKIPPED"
    nurse_sms_status = "SKIPPED"
    nurse_email_status = "SKIPPED"

    # Texte RGPD-safe
    text_patient = build_sms_text_status_only(
        prescription=prescription,
        old_status=old_status,
        new_status=new_status,
    )
    text_nurse = "[Ordo] Mise à jour: statut ordonnance (patient) : " + f"{_status_label_fr(old_status)} → {_status_label_fr(new_status)}."

    pc = (patient_channel or "NONE").upper()
    if pc in ("SMS", "BOTH"):
        if patient_phone:
            try:
                send_sms_logged(
                    to_e164=patient_phone,
                    text=text_patient,
                    purpose=SmsPurpose.INFO,
                    template_key="status_update_patient",
                    prescription=prescription,
                )
                patient_sms_status = "SENT"
            except Exception:
                patient_sms_status = "FAILED"
        else:
            patient_sms_status = "FAILED"

    if pc in ("EMAIL", "BOTH"):
        # compat: peut renvoyer str ou None
        ret = _send_email_if_possible(
            to_email=(patient_email or ""),
            subject="Mise à jour du statut de votre ordonnance",
            body=text_patient,
        )
        patient_email_status = _email_status_from_helper(ret)

    if not nurse:
        nurse_sms_status = "SKIPPED"
        nurse_email_status = "SKIPPED"
    else:
        nc = (nurse_channel or "NONE").upper()
        if nc in ("SMS", "BOTH"):
            if nurse_phone:
                try:
                    send_sms_logged(
                        to_e164=nurse_phone,
                        text=text_nurse,
                        purpose=SmsPurpose.INFO,
                        template_key="status_update_nurse",
                        prescription=prescription,
                    )
                    nurse_sms_status = "SENT"
                except Exception:
                    nurse_sms_status = "FAILED"
            else:
                nurse_sms_status = "FAILED"

        if nc in ("EMAIL", "BOTH"):
            ret = _send_email_if_possible(
                to_email=(nurse_email or ""),
                subject="Mise à jour du statut d'une ordonnance",
                body=text_nurse,
            )
            nurse_email_status = _email_status_from_helper(ret)

    return build_notification_result_summary(
        prescription=prescription,
        patient_channel=patient_channel,
        nurse_channel=nurse_channel,
        patient_sms_status=patient_sms_status,
        patient_email_status=patient_email_status,
        nurse_sms_status=nurse_sms_status,
        nurse_email_status=nurse_email_status,
    )
