from pathlib import Path
from datetime import datetime
import shutil
import re
import py_compile
import sys

BASE_DIR = Path.cwd()
NOW = datetime.now().strftime("%Y%m%d_%H%M%S")

service = BASE_DIR / "core_emails/services_renewal_v10.py"
template = BASE_DIR / "core_emails/templates/core_emails/renewals_dashboard_v10.html"

backup_dir = BASE_DIR / "backups" / "ordo_v10" / f"{NOW}_008_lien_ordonnance"
backup_dir.mkdir(parents=True, exist_ok=True)

for p in [service, template]:
    dest = backup_dir / p.relative_to(BASE_DIR)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, dest)
    print(f"📦 Backup : {dest}")

text = service.read_text(encoding="utf-8")

new_block = r'''
def _prescription_url(prescription):
    if not prescription:
        return "#"

    try:
        if hasattr(prescription, "get_absolute_url"):
            return prescription.get_absolute_url()
    except Exception:
        pass

    pk = getattr(prescription, "pk", None) or getattr(prescription, "id", None)

    if pk:
        return f"/prescriptions/{pk}/"

    return "#"


def _format_item(item):
    """
    Transforme une donnée V9 brute en ligne lisible et cliquable.
    """
    if not isinstance(item, dict):
        return {
            "title": str(item),
            "url": "#",
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
    url = _prescription_url(prescription)

    if reason == "RETARD":
        action = "Appeler le patient"
    elif reason == "DERNIER_RENOUVELLEMENT":
        action = "Contrôler le dernier renouvellement"
    else:
        action = "Contrôler le dossier"

    return {
        "title": title,
        "url": url,
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

pattern = re.compile(r"def _format_item\(item\):.*?def _format_list\(items, limit=10\):.*?return \[\]", re.S)

if pattern.search(text):
    text = pattern.sub(new_block.strip(), text)
else:
    print("❌ Bloc _format_item introuvable.")
    sys.exit(1)

service.write_text(text, encoding="utf-8")

html = template.read_text(encoding="utf-8")

html = html.replace(
    "<strong>{{ item.title }}</strong>",
    '<strong><a href="{{ item.url }}" style="color: #0a8f3c; text-decoration: none;">{{ item.title }}</a></strong>'
)

if "Ouvrir ordonnance" not in html:
    html = html.replace(
        "<p>Action recommandée : {{ item.action }}</p>",
        '<p>Action recommandée : {{ item.action }}</p>\n      <p><a href="{{ item.url }}" style="color: #0a8f3c; font-weight: bold;">Ouvrir ordonnance</a></p>'
    )

template.write_text(html, encoding="utf-8")

try:
    py_compile.compile(str(service), doraise=True)
    print("✅ Syntaxe service OK")
except Exception as e:
    print("❌ Erreur syntaxe :", e)
    sys.exit(1)

print("=" * 70)
print("✅ SCRIPT 008 TERMINÉ")
print("Lien vert vers l’ordonnance ajouté.")
print("=" * 70)
