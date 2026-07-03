from pathlib import Path
from datetime import datetime
import shutil
import sys
import re
import py_compile

BASE_DIR = Path.cwd()
NOW = datetime.now().strftime("%Y%m%d_%H%M%S")

print("=" * 70)
print("ORDO V10 - 006 BRANCHEMENT DASHBOARD V10")
print("=" * 70)

required = [
    "manage.py",
    "core_emails/views.py",
    "core_emails/services_renewal_v10.py",
    "core_emails/templates/core_emails/renewals_dashboard_v10.html",
]

missing = [x for x in required if not (BASE_DIR / x).exists()]
if missing:
    print("❌ Fichiers manquants :")
    for x in missing:
        print(" -", x)
    sys.exit(1)

views_path = BASE_DIR / "core_emails" / "views.py"

backup_dir = BASE_DIR / "backups" / "ordo_v10" / f"{NOW}_006_branch_dashboard_v10"
backup_file = backup_dir / "core_emails" / "views.py"
backup_file.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(views_path, backup_file)

print(f"📦 Backup créé : {backup_file}")

content = views_path.read_text(encoding="utf-8")

if "services_renewal_v10 import compute_renewals_dashboard_v10" not in content:
    content = (
        "from core_emails.services_renewal_v10 import compute_renewals_dashboard_v10\n"
        + content
    )
    print("✅ Import V10 ajouté.")
else:
    print("ℹ️ Import V10 déjà présent.")

pattern = re.compile(
    r"def\s+renewals_dashboard\s*\([^)]*\):\n(?P<body>(?:[ \t]+.*\n|[ \t]*\n)+)",
    re.MULTILINE
)

match = pattern.search(content)

if not match:
    print("❌ Fonction renewals_dashboard introuvable dans core_emails/views.py")
    sys.exit(1)

new_function = '''def renewals_dashboard(request):
    """
    ORDO V10 - Dashboard Renouvellements lecture seule.

    Cette vue utilise le service V10 sans modifier le moteur V9.
    """
    context = compute_renewals_dashboard_v10()
    return render(request, "core_emails/renewals_dashboard_v10.html", context)

'''

old_function = match.group(0)

if 'renewals_dashboard_v10.html' in old_function:
    print("ℹ️ La vue est déjà branchée sur le Dashboard V10.")
else:
    content = content[:match.start()] + new_function + content[match.end():]
    views_path.write_text(content, encoding="utf-8")
    print("✅ Vue renewals_dashboard branchée sur V10.")

try:
    py_compile.compile(str(views_path), doraise=True)
    print("✅ Syntaxe views.py OK")
except Exception as e:
    print("❌ Erreur syntaxe views.py :", e)
    print("Restauration automatique du backup...")
    shutil.copy2(backup_file, views_path)
    sys.exit(1)

log_file = BASE_DIR / "scripts" / "v10" / "migrations.log"
with log_file.open("a", encoding="utf-8") as f:
    f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 006_branch_dashboard_v10 | OK | backup={backup_file}\n")

print("=" * 70)
print("✅ SCRIPT 006 TERMINÉ")
print("Dashboard Renouvellements branché sur V10.")
print("Pour tester : python manage.py runserver")
print("=" * 70)
