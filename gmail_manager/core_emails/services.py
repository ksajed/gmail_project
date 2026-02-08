import re
import logging
logger_notif = logging.getLogger('ordo.notifications')

# =====================================================
# NOTIFICATIONS — JOURNALISATION MÉTIER (V8)
# =====================================================

# ORDO_NOTIF_JOURNAL:BEGIN
def _mask_destination(dest: str) -> str:
    # Masquage RGPD : destination minimisée
    # - phone: +33******501
    # - email: kh***@gmail.com
    try:
        if not dest:
            return ''
        d = str(dest).strip()
        if '@' in d:
            left, dom = d.split('@', 1)
            if len(left) <= 2:
                return ('*' * len(left)) + '@' + dom
            return left[:2] + '***@' + dom
        digits = re.sub(r'[^\d+]', '', d)
        if digits.startswith('+') and len(digits) >= 6:
            return digits[:3] + '******' + digits[-3:]
        if len(digits) >= 4:
            return '******' + digits[-3:]
        return '******'
    except Exception:
        return '******'

def log_notification_event_safe(*, prescription, recipient_type: str, channel: str, destination: str, result: str, error_message: str = '', user=None, trigger: str = 'STATUS_CHANGE'):
    # Journalisation robuste : ne doit jamais casser le flow
    masked = _mask_destination(destination or '')
    pid = getattr(prescription, 'id', None)
    try:
        logger_notif.info(
            'notif_event pid=%s recipient=%s channel=%s result=%s dest=%s trigger=%s err=%s',
            pid, recipient_type, channel, result, masked, trigger, (error_message or '')[:200],
        )
    except Exception:
        pass
    try:
        from core_emails.models import PrescriptionNotificationEvent
        PrescriptionNotificationEvent.objects.create(
            prescription=prescription,
            recipient_type=recipient_type,
            channel=channel,
            destination=masked,
            result=result,
            error_message=(error_message or '')[:500],
            created_by=user if getattr(user, 'is_authenticated', False) else None,
        )
    except Exception:
        pass

def log_status_history_notification_summary_safe(*, prescription, comment: str, user=None):
    # Historique opposable : résumé (pas de contenu médical, pas de nom patient)
    try:
        from core_emails.models import PrescriptionStatusHistory
        PrescriptionStatusHistory.objects.create(
            prescription=prescription,
            old_status=prescription.status,
            new_status=prescription.status,
            changed_by=user if getattr(user, 'is_authenticated', False) else None,
            comment=(comment or '')[:500],
        )
    except Exception:
        pass
# ORDO_NOTIF_JOURNAL:END
def _mask_phone(phone: str) -> str:
    """Masque un numéro E.164/FR pour logs métier (RGPD)."""
    if not phone:
        return "—"
    p = str(phone).strip()
    if len(p) <= 6:
        return "***"
    return p[:3] + "****" + p[-3:]

def _mask_email(email: str) -> str:
    """Masque un email pour logs métier (RGPD)."""
    if not email:
        return "—"
    e = str(email).strip()
    if "@" not in e:
        return "***"
    name, dom = e.split("@", 1)
    if len(name) <= 2:
        name_m = "*"
    else:
        name_m = name[:1] + "***" + name[-1:]
    return name_m + "@" + dom

def _log_notification_business(prescription, user, recipient_type: str, channel: str, destination: str,
                               result: str, error_message: str = "", provider_message_id: str = "", trigger: str = "") -> None:
    """
    Journalisation métier opposable:
    - PrescriptionStatusHistory (toujours)
    - PrescriptionNotificationEvent (best-effort, ne doit jamais casser)
    """
    try:
        from core_emails.models import PrescriptionStatusHistory
        # Trace opposable
        parts = [
            "Notif",
            f"trigger={trigger or '—'}",
            f"to={recipient_type}",
            f"ch={channel}",
            f"res={result}",
            f"dst={destination}",
        ]
        if provider_message_id:
            parts.append(f"provider_id={provider_message_id}")
        if error_message:
            parts.append(f"err={error_message[:120]}")
        PrescriptionStatusHistory.objects.create(
            prescription=prescription,
            old_status=prescription.status,
            new_status=prescription.status,
            changed_by=user,
            comment=" | ".join(parts),
        )
    except Exception:
        # Jamais casser le flux métier
        try:
            logger.exception("Journalisation métier: PrescriptionStatusHistory failed (prescription_id=%s)", getattr(prescription, "id", None))
        except Exception:
            pass

    # Best-effort: modèle Event si dispo
    try:
        from core_emails.models import PrescriptionNotificationEvent
        PrescriptionNotificationEvent.objects.create(
            prescription=prescription,
            recipient_type=recipient_type,
            channel=channel,
            destination=destination,
            result=result,
            error_message=error_message or "",
            created_by=user,
        )
    except Exception:
        # Ne jamais casser
        try:
            logger.info("Journalisation Event ignorée (modèle/contraintes). prescription_id=%s", getattr(prescription, "id", None))
        except Exception:
            pass
from django.db import transaction
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import PrescriptionStatusHistory
from .states import (
    PrescriptionStatusEnum,
    PRESCRIPTION_STATUS_TRANSITIONS,
)

from core_notifications.services import notify_users
from core_emails.emailing import send_status_email

import datetime
from django.utils import timezone

from .models import Prescription, PrescriptionType, PrescriptionRenewalInfo

User = get_user_model()


def status_label(enum: PrescriptionStatusEnum) -> str:
    """
    Libellé humain à partir de l'Enum
    Ex: IN_PROGRESS → In Progress
    """
    return enum.value.replace("_", " ").title()


@transaction.atomic
def change_prescription_status(*, prescription, new_status, user=None, comment=""):
    """
    🔒 MÉTHODE UNIQUE ET OFFICIELLE POUR CHANGER UN STATUT D’ORDONNANCE

    ✔ transitions strictes
    ✔ BLOCKED → commentaire obligatoire
    ✔ ARCHIVED → état final
    ✔ historique opposable (commentaire jamais NULL)
    ✔ notifications internes
    ✔ emails patients
    """

    old_status = prescription.status

    # =====================================================
    # ⛔ STATUT IDENTIQUE
    # =====================================================
    if old_status == new_status:
        raise ValidationError(
            "Le statut sélectionné est identique au statut actuel."
        )

    # =====================================================
    # 0️⃣ VALIDATION DES STATUTS
    # =====================================================
    try:
        current_enum = PrescriptionStatusEnum(old_status)
        target_enum = PrescriptionStatusEnum(new_status)
    except ValueError:
        raise ValidationError("Statut d’ordonnance invalide.")

    # =====================================================
    # 🔒 ARCHIVED = FINAL
    # =====================================================
    if current_enum == PrescriptionStatusEnum.ARCHIVED:
        raise ValidationError(
            "Cette ordonnance est archivée et ne peut plus être modifiée."
        )

    # =====================================================
    # 🔄 TRANSITION AUTORISÉE
    # =====================================================
    allowed_transitions = PRESCRIPTION_STATUS_TRANSITIONS.get(
        current_enum, set()
    )

    if target_enum not in allowed_transitions:
        raise ValidationError(
            f"Transition interdite : "
            f"{status_label(current_enum)} → {status_label(target_enum)}"
        )

    # =====================================================
    # ❗ BLOCKED → COMMENTAIRE OBLIGATOIRE
    # =====================================================
    if target_enum == PrescriptionStatusEnum.BLOCKED and not comment.strip():
        raise ValidationError(
            "Un commentaire est obligatoire pour bloquer une ordonnance."
        )

    # =====================================================
    # 📝 COMMENTAIRE GARANTI (ANTI-NULL)
    # =====================================================
    final_comment = comment.strip()
    if not final_comment:
        final_comment = (
            f"Changement de statut : "
            f"{status_label(current_enum)} → {status_label(target_enum)}"
        )

    # =====================================================
    # 1️⃣ HISTORIQUE OPPOSABLE
    # =====================================================
    PrescriptionStatusHistory.objects.create(
        prescription=prescription,
        old_status=old_status,
        new_status=new_status,
        changed_by=user,
        comment=final_comment,
    )

    # =====================================================
    # 2️⃣ MISE À JOUR DU STATUT
    # =====================================================
    prescription.status = new_status
    prescription.save(update_fields=["status", "updated_at"])

    # =====================================================
    # 3️⃣ NOTIFICATION INTERNE
    # =====================================================
    notify_users(
        users=User.objects.all(),
        title="Statut d’ordonnance modifié",
        message=(
            f"Ordonnance #{prescription.id}\n"
            f"{status_label(current_enum)} → {status_label(target_enum)}"
        ),
        object_type="Prescription",
        object_id=prescription.id,
    )

    # =====================================================
    # 4️⃣ EMAIL PATIENT
    # =====================================================
    send_status_email(
        prescription=prescription,
        old_status=old_status,
        new_status=new_status,
        user=user,
    )


    # =====================================================
    # 🔔 NOTIFICATIONS PARAMÉTRÉES PAR ORDONNANCE (V8)
    # =====================================================
    settings = getattr(prescription, "notification_settings", None)
    if settings:
        from core_emails.services import send_prescription_notifications
        send_prescription_notifications(
            prescription=prescription,
            user=user,
            patient_channel=settings.patient_channel,
            nurse_channel=settings.nurse_channel,
        )

    return prescription

#====================================================

# V7 — Renouvellement J-5 / J-3 (dashboard)
# =====================================================



def compute_renewals_watch():
    """
    Renvoie (due_5, due_3, overdue) pour le dashboard.

    Logique GLOBALE (supporte renewal_times > 1):
      - prochaine échéance = established_at + (renewal_done_count + 1) * period_days
      - fin totale        = established_at + (renewal_times + 1) * period_days

    ✅ J-5 / J-3 : conditions strictes (days_left == 5 / == 3) sur la prochaine échéance.
    ✅ Overdue : échéance passée alors qu'il reste des renouvellements (remaining > 0).
    """
    import datetime
    from django.utils import timezone
    from core_emails.models import Prescription, PrescriptionType, PrescriptionRenewalInfo

    today = timezone.localtime(timezone.now()).date()
    due_5 = []
    due_3 = []
    overdue = []

    qs = (
        Prescription.objects
        .select_related("patient")
        .select_related("renewal_info")
        .filter(type=PrescriptionType.RENOUVELLEMENT)
        .filter(established_at__isnull=False)
    )

    for p in qs:
        try:
            info = p.renewal_info
        except PrescriptionRenewalInfo.DoesNotExist:
            continue

        times = int(info.renewal_times or 0)
        done = int(info.renewal_done_count or 0)
        period = int(info.period_days or 30)

        remaining = max(0, times - done)

        # fin totale (pour info)
        end_total = p.established_at + datetime.timedelta(days=(times + 1) * period)

        # date à surveiller = prochaine échéance s'il reste des renouvellements, sinon fin totale
        if remaining > 0:
            watch_date = p.established_at + datetime.timedelta(days=(done + 1) * period)
        else:
            watch_date = end_total

        days_left = (watch_date - today).days

        # attach pour templates
        p.renewal_end_date = watch_date
        p.renewal_days_left = days_left
        p.renewal_remaining = remaining
        p.renewal_final_end_date = end_total
        p.renewal_days_left_total = (end_total - today).days
        p.renewal_overdue_days = max(0, -days_left)  # positif

        # Overdue (retard)
        if days_left < 0 and remaining > 0:
            overdue.append(p)
            continue

        # ✅ tu veux garder ces conditions strictes
        if days_left == 5:
            due_5.append(p)
        if days_left == 3:
            due_3.append(p)

    due_5.sort(key=lambda x: (getattr(x, "renewal_end_date", today), x.id))
    due_3.sort(key=lambda x: (getattr(x, "renewal_end_date", today), x.id))
    overdue.sort(key=lambda x: (getattr(x, "renewal_end_date", today), x.id))

    return due_5, due_3, overdue


def compute_renewals_watch_from_delivered():
    """
    Renvoie (due_5, due_3, overdue) en se basant sur la première délivrance.

    Logique:
      - date de départ = 1er statut DELIVERED
      - prochaine échéance = delivered_at + (renewal_done_count + 1) * period_days
      - due_5/due_3 seulement si rappel J-5/J-3 pas encore envoyé
      - overdue si échéance dépassée alors qu'il reste des renouvellements
    """
    import datetime
    from django.utils import timezone
    from core_emails.models import (
        Prescription,
        PrescriptionRenewalInfo,
        PrescriptionStatus,
        PrescriptionType,
    )

    today = timezone.localtime(timezone.now()).date()
    due_5 = []
    due_3 = []
    overdue = []

    qs = (
        Prescription.objects
        .select_related("patient", "renewal_info")
        .prefetch_related("status_history")
        .filter(type=PrescriptionType.RENOUVELLEMENT)
        .filter(established_at__isnull=False)
        .exclude(status=PrescriptionStatus.ARCHIVED)
    )

    for p in qs:
        try:
            info = p.renewal_info
        except PrescriptionRenewalInfo.DoesNotExist:
            continue

        if int(info.renewal_done_count) >= int(info.renewal_times):
            continue

        delivered_dt = None
        for h in p.status_history.all().order_by("changed_at"):
            if h.new_status == PrescriptionStatus.DELIVERED:
                delivered_dt = h.changed_at
                break
        if delivered_dt is None:
            continue

        start_date = timezone.localtime(delivered_dt).date()
        next_due_date = start_date + datetime.timedelta(
            days=(int(info.renewal_done_count) + 1) * int(info.period_days)
        )
        days_left = (next_due_date - today).days

        # attach pour affichage template
        p.renewal_end_date = next_due_date
        p.renewal_days_left = days_left

        if days_left < 0:
            overdue.append(p)

        if days_left == 5 and (
            info.reminder_5_patient_email_sent_at is None
            or info.reminder_5_patient_sms_sent_at is None
        ):
            due_5.append(p)

        if days_left == 3 and (
            info.reminder_3_patient_email_sent_at is None
            or info.reminder_3_patient_sms_sent_at is None
        ):
            due_3.append(p)

    due_5.sort(key=lambda x: (getattr(x, "renewal_end_date", today), x.id))
    due_3.sort(key=lambda x: (getattr(x, "renewal_end_date", today), x.id))
    overdue.sort(key=lambda x: (getattr(x, "renewal_end_date", today), x.id))

    return due_5, due_3, overdue


# =====================================================
# 🔔 NOTIFICATIONS — SERVICE PAR ORDONNANCE (V8)
# =====================================================

def send_prescription_notifications(
    *,
    prescription,
    user,
    patient_channel,
    nurse_channel,
    trigger="",
):
    """
    Envoi conditionnel SMS / EMAIL selon le paramétrage
    STRICTEMENT lié à l'ordonnance.

    - AUCUNE configuration globale
    - Traçabilité complète via PrescriptionNotificationEvent
    """

    from django.core.mail import send_mail
    from core_notifications.services import send_sms_logged
    from core_emails.models import (
        PrescriptionNotificationEvent,
    )

    def log_event(recipient_type, channel, destination, result, error=""):
        PrescriptionNotificationEvent.objects.create(
            prescription=prescription,
            recipient_type=recipient_type,
            channel=channel,
            destination=destination or "-",
            result=result,
            error_message=error or "",
            created_by=user,
        )

    # =========================
    # PATIENT
    # =========================
    patient = getattr(prescription, "patient", None)

    if patient_channel == "NONE":
        log_event("PATIENT", "NONE", "-", "SKIPPED")
    else:
        # SMS patient
        if patient_channel in ("SMS", "BOTH"):
            phone = getattr(patient, "phone_number", None) if patient else None
            if not phone:
                log_event("PATIENT", "SMS", "-", "FAILED", "Téléphone patient manquant")
            else:
                try:
                    send_sms_logged(
                        to_e164=phone,
                        text=f"Statut ordonnance #{prescription.id} mis à jour.",
                        prescription=prescription,
                    )
                    log_event("PATIENT", "SMS", phone, "SENT")
                except Exception as e:
                    log_event("PATIENT", "SMS", phone, "FAILED", str(e))

        # EMAIL patient
        if patient_channel in ("EMAIL", "BOTH"):
            email = getattr(patient, "email", None) if patient else None
            if not email:
                log_event("PATIENT", "EMAIL", "-", "FAILED", "Email patient manquant")
            else:
                try:
                    send_mail(
                        subject="Mise à jour de votre ordonnance",
                        message=(
                            f"Le statut de votre ordonnance "
                            f"#{prescription.id} a été mis à jour."
                        ),
                        from_email=None,
                        recipient_list=[email],
                        fail_silently=False,
                    )
                    log_event("PATIENT", "EMAIL", email, "SENT")
                except Exception as e:
                    log_event("PATIENT", "EMAIL", email, "FAILED", str(e))

    # =========================
    # INFIRMIER (si associé)
    # =========================
    nurse = prescription.assigned_nurse
    if not nurse:
        return

    if nurse_channel == "NONE":
        log_event("NURSE", "NONE", "-", "SKIPPED")
        return

    # SMS infirmier
    if nurse_channel in ("SMS", "BOTH"):
        phone = getattr(nurse, "phone_number", None)
        if not phone:
            log_event("NURSE", "SMS", "-", "FAILED", "Téléphone infirmier manquant")
        else:
            try:
                send_sms_logged(
                    to_e164=phone,
                    text=f"Ordonnance #{prescription.id} mise à jour.",
                    prescription=prescription,
                )
                log_event("NURSE", "SMS", phone, "SENT")
            except Exception as e:
                log_event("NURSE", "SMS", phone, "FAILED", str(e))

    # EMAIL infirmier
    if nurse_channel in ("EMAIL", "BOTH"):
        email = getattr(nurse, "email", None)
        if not email:
            log_event("NURSE", "EMAIL", "-", "FAILED", "Email infirmier manquant")
        else:
            try:
                send_mail(
                    subject="Ordonnance mise à jour",
                    message=f"Ordonnance #{prescription.id} : statut mis à jour.",
                    from_email=None,
                    recipient_list=[email],
                    fail_silently=False,
                )
                log_event("NURSE", "EMAIL", email, "SENT")
            except Exception as e:
                log_event("NURSE", "EMAIL", email, "FAILED", str(e))
