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
