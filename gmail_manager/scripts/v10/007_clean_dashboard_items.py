from pathlib import Path
from datetime import datetime
import shutil
import py_compile
import sys

BASE_DIR = Path.cwd()
NOW = datetime.now().strftime("%Y%m%d_%H%M%S")

print("=" * 70)
print("ORDO V10 - 007 NETTOYAGE AFFICHAGE DASHBOARD")
print("=" * 70)

service = BASE_DIR / "core_emails/services_renewal_v10.py"
template = BASE_DIR / "core_emails/templates/core_emails/renewals_dashboard_v10.html"

for p in [service, template]:
    if not p.exists():
        print(f"❌ Fichier introuvable : {p}")
        sys.exit(1)

backup_dir = BASE_DIR / "backups" / "ordo_v10" / f"{NOW}_007_clean_dashboard"
backup_dir.mkdir(parents=True, exist_ok=True)

for p in [service, template]:
    dest = backup_dir / p.relative_to(BASE_DIR)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, dest)
    print(f"📦 Backup : {dest}")

text = service.read_text(encoding="utf-8")

insert = r'''

def _format_item(item):
    """
    Transforme une donnée V9 brute en ligne lisible pour le pharmacien.
    """
    if not isinstance(item, dict):
        return {
            "title": str(item),
            "due_date": "",
            "overdue_days": "",
            "reason": "",
            "action": "Contrôler le dossier",
        }

    prescription = item.get("prescription")
    cycle = item.get("cycle")
    due_date = item.get("due_date")
    overdue_days = item.get("overdue_days")
    reason = item.get("reason") or ""

    title = str(prescription or cycle or item)

    if reason == "RETARD":
        action = "Appeler le patient"
    elif reason == "DERNIER_RENOUVELLEMENT":
        action = "Contrôler le dernier renouvellement"
    else:
        action = "Contrôler le dossier"

    return {
        "title": title,
        "due_date": due_date or "",
        "overdue_days": overdue_days or "",
        "reason": reason,
        "action": action,
    }


def _format_list(items, limit=10):
    try:
        return [_format_item(x) for x in list(items)[:limit]]
    except Exception:
        return []
'''

if "def _format_item(item):" not in text:
    text = text.replace("def compute_renewals_dashboard_v10():", insert + "\n\ndef compute_renewals_dashboard_v10():")

text = text.replace(
    'dashboard["sections"]["urgent"] = urgent',
    'dashboard["sections"]["urgent"] = _format_list(urgent)'
)
text = text.replace(
    'dashboard["sections"]["overdue"] = overdue',
    'dashboard["sections"]["overdue"] = _format_list(overdue)'
)
text = text.replace(
    'dashboard["sections"]["to_check"] = to_check',
    'dashboard["sections"]["to_check"] = _format_list(to_check)'
)
text = text.replace(
    'dashboard["sections"]["active"] = active',
    'dashboard["sections"]["active"] = _format_list(active)'
)

service.write_text(text, encoding="utf-8")

html = template.read_text(encoding="utf-8")

html = html.replace(
    "<strong>{{ item }}</strong>\n      <p>Action recommandée : contrôler maintenant.</p>",
    "<strong>{{ item.title }}</strong>\n      <p>Raison : {{ item.reason }}</p>\n      <p>Date prévue : {{ item.due_date }}</p>\n      <p>Retard : {{ item.overdue_days }} jours</p>\n      <p>Action recommandée : {{ item.action }}</p>"
)

html = html.replace(
    "<strong>{{ item }}</strong>\n      <p>Renouvellement en retard. Action recommandée : appeler le patient.</p>",
    "<strong>{{ item.title }}</strong>\n      <p>Date prévue : {{ item.due_date }}</p>\n      <p>Retard : {{ item.overdue_days }} jours</p>\n      <p>Action recommandée : {{ item.action }}</p>"
)

html = html.replace(
    "<strong>{{ item }}</strong>\n      <p>Action recommandée : vérifier le renouvellement.</p>",
    "<strong>{{ item.title }}</strong>\n      <p>Raison : {{ item.reason }}</p>\n      <p>Date prévue : {{ item.due_date }}</p>\n      <p>Action recommandée : {{ item.action }}</p>"
)

template.write_text(html, encoding="utf-8")

try:
    py_compile.compile(str(service), doraise=True)
    print("✅ Syntaxe service OK")
except Exception as e:
    print("❌ Erreur syntaxe :", e)
    sys.exit(1)

log_file = BASE_DIR / "scripts" / "v10" / "migrations.log"
with log_file.open("a", encoding="utf-8") as f:
    f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 007_clean_dashboard_items | OK\n")

print("=" * 70)
print("✅ SCRIPT 007 TERMINÉ")
print("Dashboard nettoyé : affichage lisible + limité à 10 lignes.")
print("=" * 70)
