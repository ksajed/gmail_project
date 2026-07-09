from pathlib import Path
from datetime import datetime
import shutil
import py_compile
import subprocess
import sys

BASE_DIR = Path.cwd()
NOW = datetime.now().strftime("%Y%m%d_%H%M%S")

print("=" * 70)
print("ORDO V11 - 016 CREATE CORE_AUDIT")
print("=" * 70)

if not (BASE_DIR / "manage.py").exists():
    print("❌ Lance depuis le dossier manage.py")
    sys.exit(1)

app_dir = BASE_DIR / "core_audit"
backup_dir = BASE_DIR / "backups" / "ordo_v11" / f"{NOW}_016_core_audit"
backup_dir.mkdir(parents=True, exist_ok=True)

if app_dir.exists():
    shutil.copytree(app_dir, backup_dir / "core_audit")
    print(f"📦 Backup : {backup_dir / 'core_audit'}")

(app_dir / "reports").mkdir(parents=True, exist_ok=True)

files = {
    app_dir / "__init__.py": "",
    app_dir / "apps.py": '''
from django.apps import AppConfig

class CoreAuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core_audit"
''',
    app_dir / "scanner.py": '''
from django.apps import apps

def count_models():
    results = []

    for model in apps.get_models():
        try:
            count = model.objects.count()
        except Exception:
            count = None

        results.append({
            "app": model._meta.app_label,
            "model": model.__name__,
            "table": model._meta.db_table,
            "count": count,
        })

    return results
''',
    app_dir / "integrity_audit.py": '''
from django.apps import apps
from core_integrity.runner import run_integrity_for_prescription, integrity_score

def find_prescription_model():
    for model in apps.get_models():
        if model.__name__.lower() == "prescription":
            return model
    return None


def audit_prescriptions(limit=None):
    Prescription = find_prescription_model()

    if not Prescription:
        return {
            "total": 0,
            "items": [],
            "error": "Modèle Prescription introuvable",
        }

    qs = Prescription.objects.all().order_by("id")
    if limit:
        qs = qs[:limit]

    items = []

    for prescription in qs:
        results = run_integrity_for_prescription(prescription)
        score = integrity_score(results)

        if results:
            items.append({
                "prescription_id": prescription.pk,
                "prescription": str(prescription),
                "score": score,
                "results": results,
            })

    return {
        "total": Prescription.objects.count(),
        "anomalies_count": len(items),
        "items": items,
    }
''',
    app_dir / "report.py": '''
from datetime import datetime
import json
from pathlib import Path

def write_audit_report(base_dir, model_counts, integrity_report):
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = Path(base_dir) / "scripts" / "v10" / "reports" / f"{now}_global_audit"
    report_dir.mkdir(parents=True, exist_ok=True)

    data = {
        "generated_at": now,
        "model_counts": model_counts,
        "integrity": integrity_report,
    }

    json_path = report_dir / "audit_global.json"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    md = []
    md.append("# ORDO Global Audit")
    md.append("")
    md.append(f"Date : {now}")
    md.append("")
    md.append("## Modèles")
    for item in model_counts:
        md.append(f"- {item['app']}.{item['model']} : {item['count']}")

    md.append("")
    md.append("## Integrity")
    md.append(f"- Prescriptions totales : {integrity_report.get('total')}")
    md.append(f"- Prescriptions avec anomalies : {integrity_report.get('anomalies_count')}")

    md.append("")
    md.append("## Anomalies")
    for item in integrity_report.get("items", [])[:100]:
        md.append(f"### Ordonnance {item['prescription_id']} - Score {item['score']} %")
        md.append(f"{item['prescription']}")
        for r in item["results"]:
            md.append(f"- **{r.get('code')}** {r.get('severity')} : {r.get('message')}")
            md.append(f"  - Suggestion : {r.get('suggestion')}")
        md.append("")

    md_path = report_dir / "audit_global.md"
    md_path.write_text("\\n".join(md), encoding="utf-8")

    return report_dir, md_path, json_path
''',
}

for path, content in files.items():
    path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"✅ Fichier écrit : {path.relative_to(BASE_DIR)}")

for path in app_dir.rglob("*.py"):
    py_compile.compile(str(path), doraise=True)

result = subprocess.run(
    [sys.executable, "manage.py", "check"],
    cwd=BASE_DIR,
    text=True,
    capture_output=True,
)

if result.returncode != 0:
    print(result.stdout)
    print(result.stderr)
    sys.exit(1)

print("✅ Django check OK")

log_file = BASE_DIR / "scripts" / "v10" / "migrations.log"
with log_file.open("a", encoding="utf-8") as f:
    f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 016_core_audit | OK\n")

print("=" * 70)
print("✅ SCRIPT 016 TERMINÉ")
print("core_audit créé.")
print("=" * 70)
