from pathlib import Path
from datetime import datetime
import shutil
import py_compile
import subprocess
import sys

BASE_DIR = Path.cwd()
NOW = datetime.now().strftime("%Y%m%d_%H%M%S")

print("=" * 70)
print("ORDO V10 - 012 CREATION CORE_INTEGRITY")
print("=" * 70)

if not (BASE_DIR / "manage.py").exists():
    print("❌ Lance depuis le dossier manage.py")
    sys.exit(1)

app_dir = BASE_DIR / "core_integrity"
backup_dir = BASE_DIR / "backups" / "ordo_v10" / f"{NOW}_012_core_integrity"
backup_dir.mkdir(parents=True, exist_ok=True)

if app_dir.exists():
    dest = backup_dir / "core_integrity"
    shutil.copytree(app_dir, dest)
    print(f"📦 Backup core_integrity : {dest}")

(app_dir / "rules").mkdir(parents=True, exist_ok=True)

files = {
    app_dir / "__init__.py": "",
    app_dir / "apps.py": '''
from django.apps import AppConfig

class CoreIntegrityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core_integrity"
''',
    app_dir / "rule.py": '''
class IntegrityResult:
    def __init__(self, code, severity, message, obj=None, suggestion=None):
        self.code = code
        self.severity = severity
        self.message = message
        self.obj = obj
        self.suggestion = suggestion

    def to_dict(self):
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "object": str(self.obj) if self.obj else None,
            "suggestion": self.suggestion,
        }


class IntegrityRule:
    code = "BASE"
    severity = "INFO"
    description = ""

    def check(self, prescription):
        return []
''',
    app_dir / "registry.py": '''
from core_integrity.rules.p001_archived_active_cycle import P001ArchivedActiveCycleRule

def get_rules():
    return [
        P001ArchivedActiveCycleRule(),
    ]
''',
    app_dir / "runner.py": '''
from core_integrity.registry import get_rules

def run_integrity_for_prescription(prescription):
    results = []

    for rule in get_rules():
        try:
            results.extend(rule.check(prescription))
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
''',
    app_dir / "rules" / "__init__.py": "",
    app_dir / "rules" / "p001_archived_active_cycle.py": '''
from core_integrity.rule import IntegrityRule, IntegrityResult

class P001ArchivedActiveCycleRule(IntegrityRule):
    code = "P001"
    severity = "ERROR"
    description = "Prescription archivée avec cycle actif"

    ACTIVE_STATUSES = {"RECEIVED", "ACTIVE", "PENDING", "OPEN", "EN_COURS"}

    def check(self, prescription):
        results = []

        status = str(getattr(prescription, "status", "")).upper()

        if "ARCH" not in status:
            return results

        for rel in prescription._meta.related_objects:
            model_name = rel.related_model.__name__.lower()

            if "cycle" not in model_name:
                continue

            accessor = rel.get_accessor_name()

            try:
                manager = getattr(prescription, accessor)
                cycles = manager.all()
            except Exception:
                continue

            for cycle in cycles:
                cycle_status = str(getattr(cycle, "status", "")).upper()

                if cycle_status in self.ACTIVE_STATUSES:
                    results.append(
                        IntegrityResult(
                            code=self.code,
                            severity=self.severity,
                            message="Ordonnance archivée avec un cycle encore actif.",
                            obj=cycle,
                            suggestion="Vérifier si le cycle doit être clôturé ou si l'ordonnance ne doit plus être archivée.",
                        )
                    )

        return results
'''
}

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
    f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 012_core_integrity | OK | core_integrity créé\\n")

print("=" * 70)
print("✅ SCRIPT 012 TERMINÉ")
print("Module core_integrity créé avec règle P001.")
print("=" * 70)
