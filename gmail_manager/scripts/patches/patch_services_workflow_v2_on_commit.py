# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as dt
from pathlib import Path
import re
import sys


def ts() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def backup(p: Path) -> Path:
    bak = p.with_name(p.name + f".bak.{ts()}")
    bak.write_bytes(p.read_bytes())
    return bak


def main() -> int:
    root = Path.cwd()
    wf = root / "gmail_manager" / "core_emails" / "services_workflow.py"
    if not wf.exists():
        print(f"ERROR: introuvable: {wf}", file=sys.stderr)
        return 2

    txt = wf.read_text(encoding="utf-8")

    # Idempotence: si déjà patché
    if "transaction.on_commit(" in txt and "def _send_external_notifications" in txt:
        print("SKIP: services_workflow.py déjà patché (on_commit)")
        return 0

    # 1) Ajouter helper _send_external_notifications juste avant @transaction.atomic
    marker = "\n\n@transaction.atomic\n"
    if marker not in txt:
        print("ERROR: bloc '@transaction.atomic' introuvable dans services_workflow.py", file=sys.stderr)
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
        # import local pour éviter circularité
        from .services import send_prescription_notifications
        send_prescription_notifications(
            prescription=prescription,
            user=user,
            patient_channel=settings.patient_channel,
            nurse_channel=settings.nurse_channel,
        )
"""

    txt2 = txt.replace(marker, "\n\n" + helper + marker, 1)

    # 2) Remplacer l’appel direct send_status_email(...) par on_commit(...)
    # On supprime le bloc existant d'appel email + bloc notifications settings,
    # et on met un unique on_commit(lambda: _send_external_notifications(...))
    # On repère depuis "# 4️⃣ Email patient" jusqu’à la fin du bloc settings.
    pattern = r"""
\s*#\s*4️⃣\s*Email\s*patient\s*\n
(?P<email_block>.*?)
\s*#\s*5️⃣\s*Notifications\s*paramétrées\s*par\s*ordonnance\s*\(V8\)\s*\n
(?P<notif_block>.*?)
\s*return\s+prescription
"""
    m = re.search(pattern, txt2, flags=re.DOTALL | re.VERBOSE)
    if not m:
        print("ERROR: impossible de localiser le bloc Email+Notifications dans services_workflow.py", file=sys.stderr)
        return 2

    replacement = """
    # 4️⃣ Effets externes (email/SMS) après COMMIT uniquement
    transaction.on_commit(
        lambda: _send_external_notifications(
            prescription=prescription,
            old_status=old_status,
            new_status=new_status,
            user=user,
        )
    )

    return prescription
"""
    txt3 = re.sub(pattern, replacement, txt2, flags=re.DOTALL | re.VERBOSE, count=1)

    backup(wf)
    wf.write_text(txt3, encoding="utf-8")
    print("OK: services_workflow.py patché → effets externes via transaction.on_commit()")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
