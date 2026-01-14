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
