# -*- coding: utf-8 -*-
from __future__ import annotations
import datetime as dt
from pathlib import Path
import sys

def ts() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")

def backup(p: Path) -> Path:
    bak = p.with_name(p.name + f".bak.{ts()}")
    bak.write_bytes(p.read_bytes())
    return bak

def ensure_text_file(path: Path, content: str) -> tuple[bool, str]:
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if current == content:
            return False, f"SKIP: {path} déjà à jour"
        backup(path)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True, f"OK: {path.name} créé/mis à jour"

def patch_views_import(views_py: Path) -> tuple[bool, str]:
    if not views_py.exists():
        return False, f"ERROR: introuvable: {views_py}"

    txt = views_py.read_text(encoding="utf-8")
    if "from .services_workflow import change_prescription_status" in txt:
        return False, "SKIP: views.py déjà basculé sur services_workflow"

    needle = "from .services import change_prescription_status"
    if needle not in txt:
        return False, "ERROR: import attendu non trouvé dans views.py"

    new_txt = txt.replace(
        needle,
        "from .services_workflow import change_prescription_status",
        1,
    )
    backup(views_py)
    views_py.write_text(new_txt, encoding="utf-8")
    return True, "OK: views.py basculé"

def main() -> int:
    root = Path.cwd()
    gm = root / "gmail_manager"
    if (gm / "core_emails").exists():
        base = gm
    elif (root / "core_emails").exists():
        base = root
    else:
        print("ERROR: exécute depuis la racine du projet ou depuis gmail_manager/", file=sys.stderr)
        return 2

    workflow_py = base / "core_emails" / "services_workflow.py"
    views_py = base / "core_emails" / "views.py"

    workflow_content = """# -*- coding: utf-8 -*-
\"\"\"core_emails.services_workflow

Centralisation du workflow métier (statuts) pour Ordo.
\"\"\"

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import PrescriptionStatusHistory
from .states import PrescriptionStatusEnum, PRESCRIPTION_STATUS_TRANSITIONS

from core_notifications.services import notify_users
from core_emails.emailing import send_status_email

User = get_user_model()


def status_label(enum: PrescriptionStatusEnum) -> str:
    return enum.value.replace("_", " ").title()


def _status_label_fr(status: str) -> str:
    try:
        from core_emails.models import PrescriptionStatus
        return dict(PrescriptionStatus.choices).get(status, status or "—")
    except Exception:
        return status or "—"


@transaction.atomic
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

    PrescriptionStatusHistory.objects.create(
        prescription=prescription,
        old_status=old_status,
        new_status=new_status,
        changed_by=user,
        comment=final_comment,
    )

    prescription.status = new_status
    prescription.save(update_fields=["status", "updated_at"])

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

    settings = getattr(prescription, "notification_settings", None)
    if settings:
        from .services import send_prescription_notifications
        send_prescription_notifications(
            prescription=prescription,
            user=user,
            patient_channel=settings.patient_channel,
            nurse_channel=settings.nurse_channel,
        )

    return prescription
"""

    changed1, msg1 = ensure_text_file(workflow_py, workflow_content)
    print(msg1)

    changed2, msg2 = patch_views_import(views_py)
    print(msg2)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
