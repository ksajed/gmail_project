from pathlib import Path
from datetime import datetime
import shutil
import py_compile
import sys

BASE_DIR = Path.cwd()
NOW = datetime.now().strftime("%Y%m%d_%H%M%S")

print("=" * 70)
print("ORDO V10 - 004 SERVICE RENOUVELLEMENT V10")
print("=" * 70)

required = ["manage.py", "core_emails", "scripts/v10"]
missing = [x for x in required if not (BASE_DIR / x).exists()]
if missing:
    print("❌ Projet ORDO non détecté :", missing)
    sys.exit(1)

target = BASE_DIR / "core_emails" / "services_renewal_v10.py"

backup_dir = BASE_DIR / "backups" / "ordo_v10" / f"{NOW}_004_service_v10"
backup_dir.mkdir(parents=True, exist_ok=True)

if target.exists():
    backup_target = backup_dir / "core_emails" / "services_renewal_v10.py"
    backup_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, backup_target)
    print(f"📦 Backup créé : {backup_target}")

content = r'''
"""
ORDO V10 - Service de présentation Renouvellements

Ce fichier ne modifie pas le moteur V9.
Il transforme les données existantes en informations lisibles par le pharmacien.
"""

from datetime import datetime


def _empty_dashboard():
    return {
        "v10_enabled": True,
        "generated_at": datetime.now(),
        "today_activity": {
            "title": "ORDO travaille pour vous",
            "sms_sent": 0,
            "emails_sent": 0,
            "notifications_created": 0,
            "cycles_created": 0,
            "cycles_closed": 0,
            "cycles_recalculated": 0,
        },
        "pharmacist_work": {
            "patients_to_call": 0,
            "renewals_to_check": 0,
            "urgent_files": 0,
        },
        "sections": {
            "urgent": [],
            "overdue": [],
            "to_check": [],
            "active": [],
            "history": [],
        },
        "engine_status": {
            "v9_available": False,
            "source": None,
            "message": "Service V10 actif en mode lecture seule.",
        },
    }


def _safe_len(value):
    try:
        return len(value)
    except Exception:
        return 0


def _load_v9_data():
    """
    Essaie de récupérer les données V9 sans casser l'application.
    Si aucun service V9 compatible n'est trouvé, retourne {}.
    """

    candidates = [
        ("core_emails.services", "compute_renewals_watch_v9"),
        ("core_emails.services", "compute_renewals_dashboard"),
        ("core_emails.services_renewal_rules", "compute_renewals_watch_v9"),
        ("core_emails.services_renewal_rules", "compute_renewals_dashboard"),
    ]

    for module_name, function_name in candidates:
        try:
            module = __import__(module_name, fromlist=[function_name])
            func = getattr(module, function_name, None)

            if callable(func):
                data = func()
                return data or {}, f"{module_name}.{function_name}"

        except Exception:
            continue

    return {}, None


def compute_renewals_dashboard_v10():
    """
    Point d'entrée principal du Dashboard V10.

    Objectif :
    - ne pas modifier le moteur V9 ;
    - lire les données existantes ;
    - présenter le travail automatique ;
    - présenter le travail pharmacien.
    """

    dashboard = _empty_dashboard()

    v9_data, source = _load_v9_data()

    if not isinstance(v9_data, dict):
        return dashboard

    dashboard["engine_status"]["v9_available"] = bool(source)
    dashboard["engine_status"]["source"] = source

    metrics = v9_data.get("activity_metrics", {}) or {}

    dashboard["today_activity"]["sms_sent"] = (
        metrics.get("sms_sent_today")
        or metrics.get("sms_sent")
        or 0
    )

    dashboard["today_activity"]["emails_sent"] = (
        metrics.get("emails_sent_today")
        or metrics.get("emails_sent")
        or 0
    )

    dashboard["today_activity"]["notifications_created"] = (
        metrics.get("notifications_created_today")
        or metrics.get("notifications_created")
        or 0
    )

    dashboard["today_activity"]["cycles_created"] = (
        metrics.get("cycles_created_today")
        or metrics.get("cycles_created")
        or 0
    )

    dashboard["today_activity"]["cycles_closed"] = (
        metrics.get("cycles_closed_today")
        or metrics.get("cycles_closed")
        or 0
    )

    urgent = (
        v9_data.get("renewals_urgent")
        or v9_data.get("urgent")
        or []
    )

    overdue = (
        v9_data.get("renewals_overdue_v9")
        or v9_data.get("renewals_overdue")
        or v9_data.get("overdue")
        or []
    )

    to_check = (
        v9_data.get("renewals_final")
        or v9_data.get("renewals_to_check")
        or []
    )

    active = (
        v9_data.get("renewals_active")
        or v9_data.get("active")
        or []
    )

    dashboard["sections"]["urgent"] = urgent
    dashboard["sections"]["overdue"] = overdue
    dashboard["sections"]["to_check"] = to_check
    dashboard["sections"]["active"] = active

    dashboard["pharmacist_work"]["patients_to_call"] = _safe_len(overdue)
    dashboard["pharmacist_work"]["renewals_to_check"] = _safe_len(to_check)
    dashboard["pharmacist_work"]["urgent_files"] = _safe_len(urgent)

    return dashboard
'''

target.write_text(content.strip() + "\n", encoding="utf-8")
print(f"✅ Fichier créé : {target}")

try:
    py_compile.compile(str(target), doraise=True)
    print("✅ Syntaxe Python OK")
except Exception as e:
    print("❌ Erreur syntaxe :", e)
    sys.exit(1)

log_file = BASE_DIR / "scripts" / "v10" / "migrations.log"
with log_file.open("a", encoding="utf-8") as f:
    f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 004_service_v10 | OK | {target}\n")

print("=" * 70)
print("✅ SCRIPT 004 TERMINÉ")
print("Service V10 lecture seule créé.")
print("Aucun moteur V9 modifié.")
print("=" * 70)
