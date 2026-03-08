# -*- coding: utf-8 -*-
"""core_emails.services_workflow

Centralisation du workflow métier (statuts) pour Ordo.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import PrescriptionStatusHistory, PrescriptionType, PrescriptionStatus, PrescriptionRenewalInfo, PrescriptionRenewalCycle
from .states import PrescriptionStatusEnum, PRESCRIPTION_STATUS_TRANSITIONS

from core_notifications.services import notify_users
from core_emails.emailing import send_status_email

User = get_user_model()

def _get_or_create_notification_settings(prescription):
    """Retourne notification_settings, en le créant si absent (defaults NONE/NONE).

    Ne doit jamais lever d'exception (workflow robuste).
    """
    try:
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



def _send_external_notifications(*, prescription, old_status, new_status, user, history_id=None, notification_message=""):
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

    # 2) Paramètres de notification par ordonnance
    settings = _get_or_create_notification_settings(prescription)

    # ORDO_NOTIF_V9_PATCH_APPLIED: fallback message libre (si POST vide)
    try:
        if settings and not (notification_message or '').strip():
            notification_message = (getattr(settings, 'free_text_message', '') or '').strip()
    except Exception:
        pass

    # 2bis) Email legacy uniquement si aucun settings n'existe.
    # Si settings existe, patient_channel devient la seule source de vérité.
    if not settings:
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
        from .services import send_prescription_notifications
        result = send_prescription_notifications(
            prescription=prescription,
            user=user,
            old_status=old_status,
            new_status=new_status,
            patient_channel=(getattr(settings, 'patient_channel', 'NONE') if settings else 'NONE'),
            nurse_channel=(getattr(settings, 'nurse_channel', 'NONE') if settings else 'NONE'),
            notification_message=notification_message,
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


def change_prescription_status(*, prescription, new_status, user=None, comment="", notification_message=""):
    # ORDO_NOTIF_FREE_TEXT_V2_BACKEND: message libre optionnel transmis aux notifications
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

    nm = (notification_message or "").strip()
    if nm:
        # RGPD: ne jamais logger le contenu du message libre
        final_comment = (final_comment or "").rstrip() + "\nMessage libre ajouté."
    # ORDO_NOTIF_FREE_TEXT_V2_BACKEND: trace message libre

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

    # =====================================================
    # ORDO RENEWAL ENGINE — règle métier officielle
    # Chaque renouvellement suit :
    # Reçue → En cours → Prête → Délivrée
    # Après chaque Délivrée, si des renouvellements restent,
    # un nouveau cycle s'ouvre automatiquement en RECEIVED.
    # =====================================================
    effective_new_status = new_status

    if prescription.type == PrescriptionType.RENOUVELLEMENT and new_status == PrescriptionStatus.DELIVERED:
        renewal_info, _ = PrescriptionRenewalInfo.objects.get_or_create(prescription=prescription)

        done = int(getattr(renewal_info, "renewal_done_count", 0) or 0)
        times = int(getattr(renewal_info, "renewal_times", 0) or 0)

        # IMPORTANT :
        # cycle 1 = première délivrance (ne compte PAS comme renouvellement)
        # cycle 2 = renouvellement 1
        # cycle 3 = renouvellement 2
        # ...
        open_cycle = (
            PrescriptionRenewalCycle.objects
            .filter(prescription=prescription, closed_at__isnull=True)
            .order_by("-cycle_number")
            .first()
        )

        if open_cycle:
            current_cycle_number = int(open_cycle.cycle_number)
            cycle = open_cycle
        else:
            current_cycle_number = done + 1
            cycle, _ = PrescriptionRenewalCycle.objects.get_or_create(
                prescription=prescription,
                cycle_number=current_cycle_number,
                defaults={"status": PrescriptionStatus.DELIVERED},
            )

        cycle_update_fields = []
        if getattr(cycle, "status", None) != PrescriptionStatus.DELIVERED:
            cycle.status = PrescriptionStatus.DELIVERED
            cycle_update_fields.append("status")
        if getattr(cycle, "closed_at", None) is None:
            cycle.closed_at = timezone.now()
            cycle_update_fields.append("closed_at")
        if cycle_update_fields:
            cycle.save(update_fields=cycle_update_fields)

        # La première délivrance (cycle 1) ne compte pas comme renouvellement
        if current_cycle_number <= 1:
            done_after = 0
        else:
            done_after = current_cycle_number - 1

        renewal_info.renewal_done_count = done_after

        info_update_fields = ["renewal_done_count"]

        # last_renewal_ordered_at = seulement à partir du vrai renouvellement
        if current_cycle_number > 1:
            renewal_info.last_renewal_ordered_at = timezone.now()
            info_update_fields.append("last_renewal_ordered_at")

        renewal_info.save(update_fields=info_update_fields)

        # Tant qu'il reste des renouvellements à consommer,
        # on ouvre un nouveau cycle normal en RECEIVED.
        if done_after < times:
            next_cycle_number = current_cycle_number + 1
            next_cycle, _ = PrescriptionRenewalCycle.objects.get_or_create(
                prescription=prescription,
                cycle_number=next_cycle_number,
                defaults={"status": PrescriptionStatus.RECEIVED},
            )

            reset_fields = []
            for fname in [
                "reminder_5_patient_email_sent_at",
                "reminder_5_patient_sms_sent_at",
                "reminder_3_patient_email_sent_at",
                "reminder_3_patient_sms_sent_at",
                "doctor_email_sent_at",
            ]:
                if getattr(next_cycle, fname, None) is not None:
                    setattr(next_cycle, fname, None)
                    reset_fields.append(fname)
            if reset_fields:
                next_cycle.save(update_fields=reset_fields)

            effective_new_status = PrescriptionStatus.RECEIVED
        else:
            effective_new_status = PrescriptionStatus.ARCHIVED

    prescription.status = effective_new_status

    update_fields = ["status", "updated_at"]

    # Verrouillage structurel durable :
    # dès la première sortie de RECEIVED, l'ordonnance a commencé son traitement.
    if (
        old_status == PrescriptionStatus.RECEIVED
        and effective_new_status != PrescriptionStatus.RECEIVED
        and getattr(prescription, "processing_started_at", None) is None
    ):
        prescription.processing_started_at = timezone.now()
        update_fields.append("processing_started_at")

    prescription.save(update_fields=update_fields)

    # Effets externes AFTER COMMIT (emails + notifications + NotifResult append)
    def _after_commit():
        _send_external_notifications(
            prescription=prescription,
            old_status=old_status,
            new_status=new_status,
            user=user,
            history_id=history.id,
              notification_message=notification_message,
        )
    transaction.on_commit(_after_commit)

    return prescription
