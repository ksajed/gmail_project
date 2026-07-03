from pathlib import Path
from datetime import datetime
import shutil
import py_compile
import subprocess
import sys

BASE_DIR = Path.cwd()
NOW = datetime.now().strftime("%Y%m%d_%H%M%S")

print("=" * 70)
print("ORDO V10 - 014 INTEGRITY CONTEXT + P002")
print("=" * 70)

app_dir = BASE_DIR / "core_integrity"
if not app_dir.exists():
    print("❌ core_integrity introuvable")
    sys.exit(1)

backup_dir = BASE_DIR / "backups" / "ordo_v10" / f"{NOW}_014_integrity_context_p002"
shutil.copytree(app_dir, backup_dir / "core_integrity")
print(f"📦 Backup : {backup_dir}")

files = {
    app_dir / "context.py": '''
class IntegrityContext:
    def __init__(self, prescription):
        self.prescription = prescription
        self.cycles = self._load_related("cycle")
        self.notifications = self._load_related("notification")
        self.sms = self._load_related("sms")
        self.emails = self._load_related("email")

    def _load_related(self, keyword):
        items = []

        for rel in self.prescription._meta.related_objects:
            model_name = rel.related_model.__name__.lower()

            if keyword not in model_name:
                continue

            try:
                manager = getattr(self.prescription, rel.get_accessor_name())
                items.extend(list(manager.all()))
            except Exception:
                continue

        return items

    @property
    def prescription_status(self):
        return str(getattr(self.prescription, "status", "")).upper()

    @property
    def is_archived(self):
        return "ARCH" in self.prescription_status
''',

    app_dir / "rules" / "p002_archived_in_dashboard.py": '''
from core_integrity.rule import IntegrityRule, IntegrityResult

class P002ArchivedInDashboardRule(IntegrityRule):
    code = "P002"
    severity = "ERROR"
    description = "Prescription archivée présente dans les urgences"

    def check(self, context):
        prescription = context.prescription

        if not context.is_archived:
            return []

        return [
            IntegrityResult(
                code=self.code,
                severity=self.severity,
                message="Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.",
                obj=prescription,
                suggestion="Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.",
            )
        ]
''',

    app_dir / "registry.py": '''
from core_integrity.rules.p001_archived_active_cycle import P001ArchivedActiveCycleRule
from core_integrity.rules.p002_archived_in_dashboard import P002ArchivedInDashboardRule

def get_rules():
    return [
        P001ArchivedActiveCycleRule(),
        P002ArchivedInDashboardRule(),
    ]
''',

    app_dir / "runner.py": '''
from core_integrity.registry import get_rules
from core_integrity.context import IntegrityContext

def run_integrity_for_prescription(prescription):
    context = IntegrityContext(prescription)
    results = []

    for rule in get_rules():
        try:
            results.extend(rule.check(context))
        except Exception as e:
            results.append({
                "code": "ENGINE_ERROR",
                "severity": "ERROR",
                "message": f"Erreur règle {rule.code}: {e}",
                "object": str(prescription),
                "suggestion": "Vérifier la règle d'intégrité.",
            })

    return [
        r.to_dict() if hasattr(r, "to_dict") else r
        for r in results
    ]


def integrity_score(results):
    score = 100

    for r in results:
        if r.get("severity") == "ERROR":
            score -= 25
        elif r.get("severity") == "WARNING":
            score -= 10

    return max(score, 0)
'''
}

# Adapter P001 pour recevoir context au lieu de prescription
p001 = app_dir / "rules" / "p001_archived_active_cycle.py"
txt = p001.read_text(encoding="utf-8")
txt = txt.replace("def check(self, prescription):", "def check(self, context):")
txt = txt.replace('status = str(getattr(prescription, "status", "")).upper()', 'prescription = context.prescription\n        status = context.prescription_status')
p001.write_text(txt, encoding="utf-8")

for path, content in files.items():
    path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"✅ Fichier écrit : {path.relative_to(BASE_DIR)}")

for path in app_dir.rglob("*.py"):
    py_compile.compile(str(path), doraise=True)

print("✅ Syntaxe Python OK")

result = subprocess.run(
    [sys.executable, "manage.py", "check"],
    cwd=BASE_DIR,
    text=True,
    capture_output=True,
)

if result.returncode != 0:
    print("❌ Django check erreur")
    print(result.stdout)
    print(result.stderr)
    sys.exit(1)

print("✅ Django check OK")

log_file = BASE_DIR / "scripts" / "v10" / "migrations.log"
with log_file.open("a", encoding="utf-8") as f:
    f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 014_integrity_context_p002 | OK\\n")

print("=" * 70)
print("✅ SCRIPT 014 TERMINÉ")
print("Contexte Integrity ajouté + règle P002 active.")
print("Test : python scripts/v10/011_inspector.py 17")
print("=" * 70)
