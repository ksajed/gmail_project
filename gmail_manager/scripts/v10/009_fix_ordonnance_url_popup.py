from pathlib import Path
from datetime import datetime
import shutil
import py_compile
import subprocess
import sys

BASE_DIR = Path.cwd()
NOW = datetime.now().strftime("%Y%m%d_%H%M%S")

print("=" * 70)
print("ORDO V10 - 009 LIEN ORDONNANCE DJANGO + NOUVEL ONGLET")
print("=" * 70)

service = BASE_DIR / "core_emails/services_renewal_v10.py"
template = BASE_DIR / "core_emails/templates/core_emails/renewals_dashboard_v10.html"

required = [BASE_DIR / "manage.py", service, template]
missing = [str(p) for p in required if not p.exists()]

if missing:
    print("❌ Fichiers manquants :")
    for m in missing:
        print(" -", m)
    sys.exit(1)

backup_dir = BASE_DIR / "backups" / "ordo_v10" / f"{NOW}_009_fix_ordonnance_url_popup"
backup_dir.mkdir(parents=True, exist_ok=True)

for p in [service, template]:
    dest = backup_dir / p.relative_to(BASE_DIR)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, dest)
    print(f"📦 Backup : {dest}")

text = service.read_text(encoding="utf-8")

if "from django.urls import reverse" not in text:
    text = text.replace(
        "from datetime import datetime",
        "from datetime import datetime\nfrom django.urls import reverse"
    )

old = '''def _prescription_url(prescription):
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
'''

new = '''def _prescription_url(prescription):
    """
    Retourne l'URL Django officielle de la fiche ordonnance.

    Important :
    - aucune URL codée en dur ;
    - utilise la route nommée prescription_detail ;
    - évite les erreurs du type /prescriptions/561/.
    """
    if not prescription:
        return "#"

    pk = getattr(prescription, "pk", None) or getattr(prescription, "id", None)

    if not pk:
        return "#"

    try:
        return reverse("prescription_detail", args=[pk])
    except Exception:
        return "#"
'''

if old not in text:
    print("⚠️ Bloc _prescription_url exact non trouvé.")
    print("Tentative de remplacement sécurisé par détection large...")

    start = text.find("def _prescription_url(prescription):")
    end = text.find("\ndef _format_item(item):", start)

    if start == -1 or end == -1:
        print("❌ Impossible de trouver _prescription_url.")
        sys.exit(1)

    text = text[:start] + new + text[end:]
else:
    text = text.replace(old, new)

if '"prescription_id":' not in text:
    text = text.replace(
        '"title": title,\n        "url": url,',
        '"title": title,\n        "prescription_id": getattr(prescription, "pk", None) or getattr(prescription, "id", None),\n        "url": url,'
    )

service.write_text(text, encoding="utf-8")

html = template.read_text(encoding="utf-8")

html = html.replace(
    '<a href="{{ item.url }}" style="color: #0a8f3c; text-decoration: none;">{{ item.title }}</a>',
    '<a href="{{ item.url }}" target="_blank" rel="noopener" style="color: #0a8f3c; text-decoration: none;">{{ item.title }}</a>'
)

html = html.replace(
    '<a href="{{ item.url }}" style="color: #0a8f3c; font-weight: bold;">Ouvrir ordonnance</a>',
    '<a href="{{ item.url }}" target="_blank" rel="noopener" style="display:inline-block;background:#0a8f3c;color:white;padding:8px 12px;border-radius:6px;text-decoration:none;font-weight:bold;">📄 Ouvrir ordonnance</a>'
)

template.write_text(html, encoding="utf-8")

try:
    py_compile.compile(str(service), doraise=True)
    print("✅ Syntaxe service OK")
except Exception as e:
    print("❌ Erreur syntaxe service :", e)
    sys.exit(1)

print("🔎 Vérification Django...")
result = subprocess.run(
    [sys.executable, "manage.py", "check"],
    cwd=BASE_DIR,
    text=True,
    capture_output=True,
)

if result.returncode != 0:
    print("❌ manage.py check a échoué")
    print(result.stdout)
    print(result.stderr)
    sys.exit(1)

print("✅ Django check OK")

log_file = BASE_DIR / "scripts" / "v10" / "migrations.log"
with log_file.open("a", encoding="utf-8") as f:
    f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 009_fix_ordonnance_url_popup | OK | backup={backup_dir}\n")

print("=" * 70)
print("✅ SCRIPT 009 TERMINÉ")
print("Lien ordonnance corrigé avec reverse('prescription_detail').")
print("Ouverture dans un nouvel onglet activée.")
print("=" * 70)
