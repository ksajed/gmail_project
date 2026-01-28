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
def change_prescription_status(*, prescription, new_status, user=None, comment="", notify_patient_email: bool = True):
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
    # DELIVERED_GUARD:BEGIN
    # Message métier plus clair: on autorise DELIVERED uniquement depuis READY
    if target_enum == PrescriptionStatusEnum.DELIVERED and current_enum != PrescriptionStatusEnum.READY:
        raise ValidationError("La délivrance n’est possible que depuis le statut READY.")
    # DELIVERED_GUARD:END

    allowed_transitions = PRESCRIPTION_STATUS_TRANSITIONS.get(
        current_enum, set()
    )

    if target_enum not in allowed_transitions:
        raise ValidationError(
            f"Transition interdite : "
            f"{status_label(current_enum)} → {status_label(target_enum)}"
        )

    # =====================================================
    # RENEWAL_DELIVERED_RESET:BEGIN
    renewal_ctx = None
    if (
        target_enum == PrescriptionStatusEnum.DELIVERED
        and getattr(prescription, "type", None) == PrescriptionType.RENOUVELLEMENT
    ):
        try:
            info, _ = PrescriptionRenewalInfo.objects.get_or_create(prescription=prescription)
            renewal_times = int(getattr(info, "renewal_times", 0) or 0)
            delivered_before = PrescriptionStatusHistory.objects.filter(
                prescription=prescription,
                old_status=PrescriptionStatusEnum.READY.value,
                new_status=PrescriptionStatusEnum.DELIVERED.value,
            ).count()
            renewal_ctx = {
                "info": info,
                "renewal_times": renewal_times,
                "delivered_before": delivered_before,
            }
        except Exception:
            renewal_ctx = None
    # RENEWAL_DELIVERED_RESET:END

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

    # RENEWAL_DELIVERED_RESET_POST:BEGIN
    if renewal_ctx:
        info = renewal_ctx.get("info")
        times = int(renewal_ctx.get("renewal_times") or 0)
        delivered_before = int(renewal_ctx.get("delivered_before") or 0)

        # cycles = 1ère délivrance + renouvellements
        total_cycles = max(1, int(times) + 1)
        cycle_number = int(delivered_before) + 1  # cette délivrance
        is_last_cycle = cycle_number >= total_cycles

        # done_count = nb de renouvellements déjà réalisés (= cycles - 1), borné à [0..times]
        try:
            done_effective = max(0, int(cycle_number) - 1)
            if times >= 0:
                done_effective = min(int(times), done_effective)
        except Exception:
            done_effective = int(getattr(info, "renewal_done_count", 0) or 0)

        update_fields = []
        if info is not None and hasattr(info, "renewal_done_count"):
            current_done = int(getattr(info, "renewal_done_count", 0) or 0)
            if done_effective != current_done:
                info.renewal_done_count = done_effective
                update_fields.append("renewal_done_count")

            # last_renewal_ordered_at à partir du 1er renouvellement (donc done_effective >= 1)
            if done_effective >= 1 and hasattr(info, "last_renewal_ordered_at"):
                info.last_renewal_ordered_at = timezone.now()
                update_fields.append("last_renewal_ordered_at")

        if update_fields:
            # dedup update_fields
            update_fields = list(dict.fromkeys(update_fields))
            try:
                info.save(update_fields=update_fields)
            except Exception:
                try:
                    info.save()
                except Exception:
                    pass

        # ✅ Reset statut uniquement si ce n’est PAS le dernier cycle
        if not is_last_cycle:
            try:
                PrescriptionStatusHistory.objects.create(
                    prescription=prescription,
                    old_status=PrescriptionStatusEnum.DELIVERED.value,
                    new_status=PrescriptionStatusEnum.RECEIVED.value,
                    changed_by=user,
                    comment=(
                        f"Renouvellement: délivrance enregistrée (n°{cycle_number}/{total_cycles}). "
                        f"Statut réinitialisé pour le prochain cycle."
                    ),
                )
            except Exception:
                pass

            try:
                prescription.status = PrescriptionStatusEnum.RECEIVED.value
                prescription.save(update_fields=["status", "updated_at"])
            except Exception:
                pass
# RENEWAL_DELIVERED_RESET_POST:END




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
            if h.old_status == PrescriptionStatus.READY and h.new_status == PrescriptionStatus.DELIVERED:
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
