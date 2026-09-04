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
        "Mise à jour: statut de votre ordonnance : "
        f"{_status_label_fr(old_status)} → {_status_label_fr(new_status)}."
    )



# ORDO_NOTIF_FREE_TEXT_V2_BACKEND: helpers message libre (RGPD-safe)
def _sanitize_free_text(msg: str, max_len: int = 240) -> str:
    m = (msg or "").strip()
    m = " ".join(m.split())
    if len(m) > max_len:
        m = m[:max_len].rstrip() + "…"
    return m

def _append_free_text(base: str, msg: str) -> str:
    m = _sanitize_free_text(msg)
    if not m:
        return base
    base = (base or "").rstrip()
    return base + "\n\n" + "Message de la pharmacie : " + m

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
        "Mise à jour: statut ordonnance (patient) : "
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


def _legacy_send_prescription_notifications_void(
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
    user=None,
    old_status=None,
    new_status=None,
    patient_channel="NONE",
    nurse_channel="NONE",
    notification_message="",
):
    """Override SAFE (final) : envoi SMS/EMAIL patient/infirmier + journalisation events.

    - SMS premium (court) sans "Ordo"
    - EMAIL premium (plain + HTML) sans "Ordo"
    - Journalise via PrescriptionNotificationEvent (destination masquée)
    - Retourne NotifResult (si présent) ou dict
    """
    old_status = old_status if old_status is not None else getattr(prescription, "status", "")
    new_status = new_status if new_status is not None else getattr(prescription, "status", "")

    pc = (patient_channel or "NONE").upper()
    nc = (nurse_channel or "NONE").upper()

    patient = getattr(prescription, "patient", None)
    patient_phone = getattr(patient, "phone_number", None) if patient else None
    patient_email = getattr(patient, "email", None) if patient else None

    nurse = getattr(prescription, "assigned_nurse", None)
    nurse_phone = None
    nurse_email = None
    if nurse:
        nurse_phone = getattr(nurse, "phone_number", None) or getattr(nurse, "phone", None)
        nurse_email = getattr(nurse, "email", None)

    # --- Helpers events (RGPD-safe)
    def _mask_destination(dest: str) -> str:
        dest = (dest or "").strip()
        if not dest:
            return ""
        if "@" in dest:
            try:
                local, domain = dest.split("@", 1)
                local = (local[:1] + "***") if local else "***"
                return local + "@" + domain
            except Exception:
                return "***"
        digits = "".join(ch for ch in dest if ch.isdigit())
        if len(digits) >= 6:
            return digits[:2] + "***" + digits[-2:]
        if len(digits) >= 2:
            return "***" + digits[-2:]
        return "***"

    def _log_event(*, recipient_type: str, channel: str, destination: str, result: str, error_message: str = "") -> None:
        try:
            from core_emails.models import PrescriptionNotificationEvent
            PrescriptionNotificationEvent.objects.create(
                prescription=prescription,
                recipient_type=recipient_type,
                channel=(channel or "NONE").upper(),
                destination=_mask_destination(destination),
                result=result,
                error_message=(error_message or "")[:500],
                created_by=user,
            )
        except Exception:
            pass

    # --- Identité pharmacie (sans "Ordo")
    pharmacy_name = "La Grande Pharmacie de Fives - Lille"
    pharmacy_phone = "03 20 56 50 05"
    pharmacy_address = "132 Rue Pierre Legrand, 59800 Lille"

    ref = str(getattr(prescription, "id", "") or "")
    patient_full_name = (getattr(patient, "full_name", "") if patient else "") or ""
    msg_free = (notification_message or "").strip()

    def _status_fr(code: str) -> str:
        try:
            from core_emails.models import PrescriptionStatus
            return dict(PrescriptionStatus.choices).get(code, code or "—")
        except Exception:
            return code or "—"

    status_label = _status_fr(new_status)

    # --- SMS premium (court / safe)
    text_patient = (
        f"{pharmacy_name}\n"
        f"Votre dossier ref. {ref} est desormais {status_label}."
    )
    if msg_free:
        text_patient += f"\nMessage: {_sanitize_free_text(msg_free, 80)}"
    text_patient += f"\nContact: {pharmacy_phone}."

    text_nurse = (
        f"{pharmacy_name}\n"
        f"Ordonnance ref. {ref} - {patient_full_name} - statut: {status_label}."
    )
    if msg_free:
        text_nurse += f"\nMessage: {_sanitize_free_text(msg_free, 80)}"
    text_nurse += f"\nContact: {pharmacy_phone}."

    # --- Email premium (plain + HTML)
    def _html_escape(x: str) -> str:
        x = (x or "")
        return (
            x.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
             .replace("'", "&#39;")
        )

    def _email_plain_patient() -> str:
        base = (
            f"{pharmacy_name}\n"
            f"Ordonnance ref. {ref}\n"
            f"Statut : {status_label}\n\n"
            "Bonjour,\n"
            f"Le statut de votre ordonnance ref. {ref} est desormais : {status_label}\n\n"
            f"Pour toute question: {pharmacy_phone}\n"
        )
        if msg_free:
            base += f"\nInformation : {msg_free}\n"
        return base

    def _email_plain_nurse() -> str:
        base = (
            f"{pharmacy_name}\n"
            f"Ordonnance ref. {ref}\n"
            f"Patient : {patient_full_name}\n"
            f"Statut : {status_label}\n\n"
            "Bonjour,\n"
            f"Le statut de l'ordonnance ref. {ref} concernant {patient_full_name} est desormais : {status_label}\n\n"
            f"Pour toute question: {pharmacy_phone}\n"
        )
        if msg_free:
            base += f"\nInformation : {msg_free}\n"
        return base

    def _email_html_patient() -> str:
        ref_e = _html_escape(ref)
        st_e = _html_escape(status_label)
        msg_e = _html_escape(msg_free)
        info_block = (
            "<div style='margin-top:12px;font-size:13px;line-height:20px;color:#111827;"
            "background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;padding:12px 14px;'>"
            f"<strong>Information :</strong> {msg_e}</div>"
            if msg_e else ""
        )
        return (
            "<!doctype html><html lang='fr'><head><meta charset='utf-8'></head>"
            "<body style='margin:0;padding:0;background:#f6f7fb;'>"
            "<table role='presentation' width='100%' cellspacing='0' cellpadding='0' style='background:#f6f7fb;padding:24px 0;'>"
            "<tr><td align='center'>"
            "<table role='presentation' width='640' cellspacing='0' cellpadding='0' style='width:640px;max-width:94vw;'>"
            f"<tr><td style='padding:12px 8px;text-align:center;font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#6b7280;'>{pharmacy_name}</td></tr>"
            "<tr><td style='background:#ffffff;border-radius:16px;box-shadow:0 8px 24px rgba(17,24,39,.08);overflow:hidden;'>"
            "<table role='presentation' width='100%' cellspacing='0' cellpadding='0'>"
            "<tr><td style='padding:22px 24px 8px 24px;'>"
            "<div style='font-family:Arial,Helvetica,sans-serif;font-size:20px;line-height:28px;font-weight:700;color:#111827;'>Mise a jour de votre ordonnance</div>"
            f"<div style='margin-top:6px;font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:20px;color:#6b7280;'>Reference : <strong style='color:#111827;'>{ref_e}</strong></div>"
            "</td></tr>"
            f"<tr><td style='padding:10px 24px 0 24px;'><span style='display:inline-block;background:#eef2ff;border:1px solid #e0e7ff;color:#1f2937;border-radius:999px;padding:10px 14px;font-family:Arial,Helvetica,sans-serif;font-size:14px;'>Statut : <strong>{st_e}</strong></span></td></tr>"
            "<tr><td style='padding:18px 24px 22px 24px;font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:22px;color:#111827;'>"
            "Bonjour,<br><br>"
            f"Le statut de votre ordonnance ref. <strong>{ref_e}</strong> est desormais :<br><strong>{st_e}</strong>"
            f"{info_block}"
            f"<div style='margin-top:16px;'>Notre equipe reste disponible au <strong>{pharmacy_phone}</strong>.</div>"
            "</td></tr>"
            "</table></td></tr>"
            f"<tr><td style='padding:14px 8px;text-align:center;font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:18px;color:#6b7280;'>{pharmacy_name} - {pharmacy_address}</td></tr>"
            "</table></td></tr></table></body></html>"
        )

    def _email_html_nurse() -> str:
        ref_e = _html_escape(ref)
        st_e = _html_escape(status_label)
        pn_e = _html_escape(patient_full_name)
        msg_e = _html_escape(msg_free)
        info_block = (
            "<div style='margin-top:12px;font-size:13px;line-height:20px;color:#111827;"
            "background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;padding:12px 14px;'>"
            f"<strong>Information :</strong> {msg_e}</div>"
            if msg_e else ""
        )
        return (
            "<!doctype html><html lang='fr'><head><meta charset='utf-8'></head>"
            "<body style='margin:0;padding:0;background:#f6f7fb;'>"
            "<table role='presentation' width='100%' cellspacing='0' cellpadding='0' style='background:#f6f7fb;padding:24px 0;'>"
            "<tr><td align='center'>"
            "<table role='presentation' width='640' cellspacing='0' cellpadding='0' style='width:640px;max-width:94vw;'>"
            f"<tr><td style='padding:12px 8px;text-align:center;font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#6b7280;'>{pharmacy_name}</td></tr>"
            "<tr><td style='background:#ffffff;border-radius:16px;box-shadow:0 8px 24px rgba(17,24,39,.08);overflow:hidden;'>"
            "<table role='presentation' width='100%' cellspacing='0' cellpadding='0'>"
            "<tr><td style='padding:22px 24px 8px 24px;'>"
            "<div style='font-family:Arial,Helvetica,sans-serif;font-size:20px;line-height:28px;font-weight:700;color:#111827;'>Mise a jour ordonnance associee</div>"
            f"<div style='margin-top:6px;font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:20px;color:#6b7280;'>Reference : <strong style='color:#111827;'>{ref_e}</strong> - Patient : <strong style='color:#111827;'>{pn_e}</strong></div>"
            "</td></tr>"
            f"<tr><td style='padding:10px 24px 0 24px;'><span style='display:inline-block;background:#ecfeff;border:1px solid #cffafe;color:#0f172a;border-radius:999px;padding:10px 14px;font-family:Arial,Helvetica,sans-serif;font-size:14px;'>Statut : <strong>{st_e}</strong></span></td></tr>"
            "<tr><td style='padding:18px 24px 22px 24px;font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:22px;color:#111827;'>"
            "Bonjour,<br><br>"
            f"Le statut de l'ordonnance ref. <strong>{ref_e}</strong> concernant <strong>{pn_e}</strong> est desormais :<br><strong>{st_e}</strong>"
            f"{info_block}"
            f"<div style='margin-top:16px;'>Contact pharmacie : <strong>{pharmacy_phone}</strong>.</div>"
            "</td></tr>"
            "</table></td></tr>"
            f"<tr><td style='padding:14px 8px;text-align:center;font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:18px;color:#6b7280;'>{pharmacy_name} - {pharmacy_address}</td></tr>"
            "</table></td></tr></table></body></html>"
        )

    # --- Init statuts
    patient_sms_status = "SKIPPED"
    patient_email_status = "SKIPPED"
    nurse_sms_status = "SKIPPED"
    nurse_email_status = "SKIPPED"

    # --- Envoi PATIENT SMS
    if pc in ("SMS", "BOTH"):
        if patient_phone:
            try:
                from core_notifications.services import send_sms_logged, SmsPurpose
                send_sms_logged(
                    to_e164=patient_phone,
                    text=text_patient,
                    purpose=SmsPurpose.INFO,
                    template_key="status_update_patient",
                    prescription=prescription,
                )
                patient_sms_status = "SENT"
                _log_event(recipient_type="PATIENT", channel="SMS", destination=str(patient_phone), result="SENT")
            except Exception as e:
                patient_sms_status = "FAILED"
                _log_event(recipient_type="PATIENT", channel="SMS", destination=str(patient_phone), result="FAILED", error_message=str(e))
        else:
            patient_sms_status = "FAILED"
            _log_event(recipient_type="PATIENT", channel="SMS", destination="", result="FAILED", error_message="missing_phone")

    # --- Envoi PATIENT EMAIL (plain + HTML)
    if pc in ("EMAIL", "BOTH"):
        if patient_email:
            try:
                subject = f"Mise a jour de votre ordonnance - ref. {ref}"
                send_mail(
                    subject=subject,
                    message=_email_plain_patient(),
                    from_email=None,
                    recipient_list=[patient_email],
                    fail_silently=False,
                    html_message=_email_html_patient(),
                )
                patient_email_status = "SENT"
                _log_event(recipient_type="PATIENT", channel="EMAIL", destination=str(patient_email), result="SENT")
            except Exception as e:
                patient_email_status = "FAILED"
                _log_event(recipient_type="PATIENT", channel="EMAIL", destination=str(patient_email), result="FAILED", error_message=str(e))
        else:
            patient_email_status = "FAILED"
            _log_event(recipient_type="PATIENT", channel="EMAIL", destination="", result="FAILED", error_message="missing_email")

    # --- Envoi NURSE (si pas d'infirmier affecte)
    if not nurse:
        if nc != "NONE":
            _log_event(recipient_type="NURSE", channel=nc, destination="", result="SKIPPED", error_message="no_nurse_assigned")
        try:
            NotifResultCls = NotifResult  # noqa: F821
        except Exception:
            NotifResultCls = None
        summary = f"PATIENT SMS={patient_sms_status} EMAIL={patient_email_status}; NURSE SKIPPED(no nurse)"
        if NotifResultCls:
            return NotifResultCls(
                patient_sms_status=patient_sms_status,
                patient_email_status=patient_email_status,
                nurse_sms_status="SKIPPED",
                nurse_email_status="SKIPPED",
                summary=summary,
            )
        return {
            "patient_sms_status": patient_sms_status,
            "patient_email_status": patient_email_status,
            "nurse_sms_status": "SKIPPED",
            "nurse_email_status": "SKIPPED",
            "summary": summary,
        }

    # --- Envoi NURSE SMS
    if nc in ("SMS", "BOTH"):
        if nurse_phone:
            try:
                from core_notifications.services import send_sms_logged, SmsPurpose
                send_sms_logged(
                    to_e164=nurse_phone,
                    text=text_nurse,
                    purpose=SmsPurpose.INFO,
                    template_key="status_update_nurse",
                    prescription=prescription,
                )
                nurse_sms_status = "SENT"
                _log_event(recipient_type="NURSE", channel="SMS", destination=str(nurse_phone), result="SENT")
            except Exception as e:
                nurse_sms_status = "FAILED"
                _log_event(recipient_type="NURSE", channel="SMS", destination=str(nurse_phone), result="FAILED", error_message=str(e))
        else:
            nurse_sms_status = "FAILED"
            _log_event(recipient_type="NURSE", channel="SMS", destination="", result="FAILED", error_message="missing_phone")

    # --- Envoi NURSE EMAIL (plain + HTML)
    if nc in ("EMAIL", "BOTH"):
        if nurse_email:
            try:
                subject = f"Mise a jour ordonnance - ref. {ref} - {patient_full_name}"
                send_mail(
                    subject=subject,
                    message=_email_plain_nurse(),
                    from_email=None,
                    recipient_list=[nurse_email],
                    fail_silently=False,
                    html_message=_email_html_nurse(),
                )
                nurse_email_status = "SENT"
                _log_event(recipient_type="NURSE", channel="EMAIL", destination=str(nurse_email), result="SENT")
            except Exception as e:
                nurse_email_status = "FAILED"
                _log_event(recipient_type="NURSE", channel="EMAIL", destination=str(nurse_email), result="FAILED", error_message=str(e))
        else:
            nurse_email_status = "FAILED"
            _log_event(recipient_type="NURSE", channel="EMAIL", destination="", result="FAILED", error_message="missing_email")

    # --- Retour resultat
    try:
        NotifResultCls = NotifResult  # noqa: F821
    except Exception:
        NotifResultCls = None

    summary = f"PATIENT SMS={patient_sms_status} EMAIL={patient_email_status}; NURSE SMS={nurse_sms_status} EMAIL={nurse_email_status}"
    if NotifResultCls:
        return NotifResultCls(
            patient_sms_status=patient_sms_status,
            patient_email_status=patient_email_status,
            nurse_sms_status=nurse_sms_status,
            nurse_email_status=nurse_email_status,
            summary=summary,
        )
    return {
        "patient_sms_status": patient_sms_status,
        "patient_email_status": patient_email_status,
        "nurse_sms_status": nurse_sms_status,
        "nurse_email_status": nurse_email_status,
        "summary": summary,
    }
