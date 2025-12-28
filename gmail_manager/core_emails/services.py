from django.db import transaction
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import (
    PrescriptionStatusHistory,
    PrescriptionStatus,
)
from .states import (
    PrescriptionStatusEnum,
    PRESCRIPTION_STATUS_TRANSITIONS,
)

from core_notifications.services import notify_users
from core_emails.emailing import send_status_email

User = get_user_model()


@transaction.atomic
def change_prescription_status(*, prescription, new_status, user=None, comment=""):
    """
    🔒 MÉTHODE UNIQUE ET OFFICIELLE POUR CHANGER UN STATUT D’ORDONNANCE

    ✔ transitions strictes (states.py)
    ✔ BLOCKED → commentaire obligatoire
    ✔ ARCHIVED → état final
    ✔ historique légal opposable
    ✔ notifications internes
    ✔ emails patients via emailing.py
    """

    # =====================================================
    # DEBUG (peut être supprimé plus tard)
    # =====================================================
    print(">>> SERVICE change_prescription_status APPELÉ <<<")
    print("STATUT RÉEL =", new_status)

    old_status = prescription.status

    # ⛔ Aucun changement réel
    if old_status == new_status:
        return prescription

    # =====================================================
    # 0️⃣ VALIDATION DES STATUTS
    # =====================================================
    try:
        current_enum = PrescriptionStatusEnum(old_status)
        target_enum = PrescriptionStatusEnum(new_status)
    except ValueError:
        raise ValidationError("Statut d’ordonnance invalide.")

    # =====================================================
    # 🔒 ARCHIVED = ÉTAT FINAL
    # =====================================================
    if current_enum == PrescriptionStatusEnum.ARCHIVED:
        raise ValidationError(
            "Cette ordonnance est archivée et ne peut plus être modifiée."
        )

    # =====================================================
    # 🔄 TRANSITION AUTORISÉE ?
    # =====================================================
    allowed_transitions = PRESCRIPTION_STATUS_TRANSITIONS.get(
        current_enum,
        set()
    )

    if target_enum not in allowed_transitions:
        raise ValidationError(
            f"Transition interdite : {current_enum.value} → {target_enum.value}"
        )

    # =====================================================
    # ❗ BLOCKED → COMMENTAIRE OBLIGATOIRE
    # =====================================================
    if target_enum == PrescriptionStatusEnum.BLOCKED and not comment.strip():
        raise ValidationError(
            "Un commentaire est obligatoire pour bloquer une ordonnance."
        )

    # =====================================================
    # 1️⃣ HISTORIQUE DES STATUTS (AUDIT OPPOSABLE)
    # =====================================================
    PrescriptionStatusHistory.objects.create(
        prescription=prescription,
        old_status=old_status,
        new_status=new_status,
        changed_by=user,
        comment=comment,
    )

    # =====================================================
    # 2️⃣ MISE À JOUR DU STATUT
    # =====================================================
    prescription.status = new_status
    prescription.save(update_fields=["status", "updated_at"])

    # =====================================================
    # 3️⃣ NOTIFICATION INTERNE (PHARMACIE)
    # =====================================================
    users = User.objects.all()

    notify_users(
        users=users,
        title="Statut d’ordonnance modifié",
        message=(
            f"Ordonnance #{prescription.id}\n"
            f"Statut : {old_status} → {new_status}\n"
            f"{comment}"
        ),
        object_type="Prescription",
        object_id=prescription.id,
    )

    # =====================================================
    # 4️⃣ EMAIL PATIENT (EMAILING CENTRALISÉ)
    # =====================================================
    send_status_email(
        prescription=prescription,
        old_status=old_status,
        new_status=new_status,
        user=user,
    )

    return prescription
