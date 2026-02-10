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


def main() -> int:
    wf = Path("gmail_manager/core_emails/services_workflow.py")
    if not wf.exists():
        print(f"ERROR: introuvable: {wf}", file=sys.stderr)
        return 2

    txt = wf.read_text(encoding="utf-8")

    # Idempotence
    if "def _send_external_notifications" in txt and "transaction.on_commit(" in txt:
        print("SKIP: services_workflow.py déjà patché (safe on_commit).")
        return 0

    # 1) Insérer helper avant @transaction.atomic
    anchor = "\n\n@transaction.atomic\n"
    if anchor not in txt:
        print("ERROR: '@transaction.atomic' introuvable.", file=sys.stderr)
        return 2

    helper = """
def _send_external_notifications(*, prescription, old_status, new_status, user):
    \"\"\"Effets externes (email/SMS) exécutés AFTER COMMIT uniquement.\"\"\"

    # Email patient (externe)
    send_status_email(
        prescription=prescription,
        old_status=old_status,
        new_status=new_status,
        user=user,
    )

    # Notifications paramétrées par ordonnance (V8) (externe: SMS/email)
    settings = getattr(prescription, "notification_settings", None)
    if settings:
        from .services import send_prescription_notifications
        send_prescription_notifications(
            prescription=prescription,
            user=user,
            patient_channel=settings.patient_channel,
            nurse_channel=settings.nurse_channel,
        )
"""

    txt = txt.replace(anchor, "\n\n" + helper + anchor, 1)

    # 2) Remplacer proprement le bloc existant par on_commit
    # On cherche les 2 ancres EXACTES présentes dans ton fichier v1:
    a = "    # 4️⃣ Email patient"
    b = "    # 5️⃣ Notifications paramétrées par ordonnance (V8)"
    r = "    return prescription"

    ia = txt.find(a)
    ib = txt.find(b)
    ir = txt.find(r)

    if ia == -1 or ib == -1 or ir == -1:
        print("ERROR: ancres Email/Notifications/return introuvables. Patch safe abandonné.", file=sys.stderr)
        return 2

    # On remplace de "# 4️⃣ Email patient" jusqu'avant "return prescription"
    before = txt[:ia]
    after = txt[ir:]  # inclut 'return prescription'

    on_commit_block = """    # 4️⃣ Effets externes (email/SMS) après COMMIT uniquement
    transaction.on_commit(
        lambda: _send_external_notifications(
            prescription=prescription,
            old_status=old_status,
            new_status=new_status,
            user=user,
        )
    )

"""

    txt = before + on_commit_block + after

    backup(wf)
    wf.write_text(txt, encoding="utf-8")
    print("OK: services_workflow.py patché (SAFE) → effets externes via transaction.on_commit()")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
