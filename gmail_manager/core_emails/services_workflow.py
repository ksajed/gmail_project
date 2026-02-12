# -*- coding: utf-8 -*-
"""core_emails.services_workflow

Centralisation du workflow métier (statuts) pour Ordo.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import PrescriptionStatusHistory
from .states import PrescriptionStatusEnum, PRESCRIPTION_STATUS_TRANSITIONS

from core_notifications.services import notify_users
from core_emails.emailing import send_status_email

User = get_user_model()

def _get_or_create_notification_settings(prescription):
    """Retourne notification_settings, en le créant si absent (defaults NONE/NONE).

    Ne doit jamais lever d'exception (workflow robuste).
    """
    try:
        settings = _get_or_create_notification_settings(prescription)
        if settings is not None:
            return settings
        from core_emails.models import PrescriptionNotificationSettings
        settings, _ = PrescriptionNotificationSettings.objects.get_or_create(
            prescription=prescription,
            defaults={"patient_channel": "NONE", "nurse_channel": "NONE"},
        )
        return settings
    except Exception:
        return None



def status_label(enum: PrescriptionStatusEnum) -> str:
    return enum.value.replace("_", " ").title()


def _status_label_fr(status: str) -> str:
    try:
        from core_emails.models import PrescriptionStatus
        return dict(PrescriptionStatus.choices).get(status, status or "—")
    except Exception:
        return status or "—"



def _send_external_notifications(*, prescription, old_status, new_status, user, history_id=None):
    """Effets externes (emails + notifications) exécutés AFTER COMMIT.

    - Envoi email statut
    - Notifications internes (dashboard)
    - Envoi SMS/Email patient/infirmier selon settings
    - Append du résultat réel dans PrescriptionStatusHistory.comment (RGPD-safe)
    """
    # 1) Notification interne (dashboard)
    try:
        notify_users(
            users=User.objects.all(),
            title="Statut d’ordonnance modifié",
            message=(
                f"Ordonnance #{prescription.id} — Statut : "
                f"{_status_label_fr(old_status)} → {_status_label_fr(new_status)}"
            ),
            object_type="Prescription",
            object_id=prescription.id,
        )
    except Exception:
        pass

    # 2) Email “statut” (si ton emailing est branché)
    try:
        send_status_email(
            prescription=prescription,
            old_status=old_status,
            new_status=new_status,
            user=user,
        )
    except Exception:
        pass

    # 3) Notifications patient/infirmier + résultat réel
    result = None
    try:
        settings = _get_or_create_notification_settings(prescription)
        if settings:
            from .services import send_prescription_notifications
            result = send_prescription_notifications(
                prescription=prescription,
                user=user,
                old_status=old_status,
                new_status=new_status,
                patient_channel=settings.patient_channel,
                nurse_channel=settings.nurse_channel,
            )
    except Exception:
        result = None

    # 4) Append NotifResult dans l'historique (après commit)
    if history_id and result:
        try:
            h = PrescriptionStatusHistory.objects.filter(id=history_id).first()
            if h:
                if "NotifResult:" in (h.comment or ""):
                    return
                h.comment = (h.comment or "").rstrip() + "\n" + str(result)
                h.save(update_fields=["comment"])
        except Exception:
            pass


def change_prescription_status(*, prescription, new_status, user=None, comment=""):
    old_status = prescription.status

    if old_status == new_status:
        raise ValidationError("Le statut sélectionné est identique au statut actuel.")

    try:
        current_enum = PrescriptionStatusEnum(old_status)
        target_enum = PrescriptionStatusEnum(new_status)
    except ValueError:
        raise ValidationError("Statut d’ordonnance invalide.")

    if current_enum == PrescriptionStatusEnum.ARCHIVED:
        raise ValidationError("Cette ordonnance est archivée et ne peut plus être modifiée.")

    allowed_transitions = PRESCRIPTION_STATUS_TRANSITIONS.get(current_enum, set())
    if target_enum not in allowed_transitions:
        raise ValidationError(
            f"Transition interdite : {status_label(current_enum)} → {status_label(target_enum)}"
        )

    if target_enum == PrescriptionStatusEnum.BLOCKED and not (comment or "").strip():
        raise ValidationError("Un commentaire est obligatoire pour bloquer une ordonnance.")

    final_comment = (comment or "").strip()
    if not final_comment:
        final_comment = f"Changement de statut : {status_label(current_enum)} → {status_label(target_enum)}"

    # Audit notifications (RGPD-safe) dans l'historique
    settings = _get_or_create_notification_settings(prescription)
    if settings:
        from .services_notifications import build_notification_audit_summary
        patient = getattr(prescription, "patient", None)
        patient_phone = getattr(patient, "phone_number", None) if patient else None
        patient_email = getattr(patient, "email", None) if patient else None

        nurse = getattr(prescription, "assigned_nurse", None)
        nurse_phone = None
        nurse_email = None
        if nurse:
            nurse_phone = getattr(nurse, "phone_number", None) or getattr(nurse, "phone", None)
            nurse_email = getattr(nurse, "email", None)

        final_comment = (
            final_comment
            + "\n"
            + build_notification_audit_summary(
                prescription=prescription,
                patient_channel=settings.patient_channel,
                nurse_channel=settings.nurse_channel,
                patient_phone=patient_phone,
                patient_email=patient_email,
                nurse_phone=nurse_phone,
                nurse_email=nurse_email,
            )
        )

    history = PrescriptionStatusHistory.objects.create(
        prescription=prescription,
        old_status=old_status,
        new_status=new_status,
        changed_by=user,
        comment=final_comment,
    )

    prescription.status = new_status
    prescription.save(update_fields=["status", "updated_at"])

    # Effets externes AFTER COMMIT (emails + notifications + NotifResult append)
    def _after_commit():
        _send_external_notifications(
            prescription=prescription,
            old_status=old_status,
            new_status=new_status,
            user=user,
            history_id=history.id,
        )
    transaction.on_commit(_after_commit)

    notify_users(
        users=User.objects.all(),
        title="Statut d’ordonnance modifié",
        message=(
            f"Ordonnance #{prescription.id} — Statut : "
            f"{_status_label_fr(old_status)} → {_status_label_fr(new_status)}"
        ),
        object_type="Prescription",
        object_id=prescription.id,
    )

    send_status_email(
        prescription=prescription,
        old_status=old_status,
        new_status=new_status,
        user=user,
    )

    settings = _get_or_create_notification_settings(prescription)
    if settings:
        from .services import send_prescription_notifications

    return prescription
