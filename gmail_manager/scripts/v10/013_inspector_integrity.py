from pathlib import Path
from datetime import datetime
import shutil
import py_compile
import sys

BASE_DIR = Path.cwd()
NOW = datetime.now().strftime("%Y%m%d_%H%M%S")

print("=" * 70)
print("ORDO V10 - 013 INSPECTOR + INTEGRITY")
print("=" * 70)

inspector = BASE_DIR / "scripts/v10/011_inspector.py"
runner = BASE_DIR / "core_integrity/runner.py"

if not inspector.exists() or not runner.exists():
    print("❌ Fichier manquant.")
    sys.exit(1)

backup_dir = BASE_DIR / "backups" / "ordo_v10" / f"{NOW}_013_inspector_integrity"
backup_dir.mkdir(parents=True, exist_ok=True)

dest = backup_dir / "scripts/v10/011_inspector.py"
dest.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(inspector, dest)
print(f"📦 Backup : {dest}")

text = inspector.read_text(encoding="utf-8")

if "from core_integrity.runner import run_integrity_for_prescription, integrity_score" not in text:
    text = text.replace(
        "from django.apps import apps",
        "from django.apps import apps\nfrom core_integrity.runner import run_integrity_for_prescription, integrity_score"
    )

old = '''    data = {
        "generated_at": NOW,
        "prescription_id": prescription_id,
        "prescription": obj_to_dict(prescription),
        "related": get_related_objects(prescription),
        "anomalies": [],
    }

    status = str(getattr(prescription, "status", "")).lower()

    if "arch" in status:
        data["anomalies"].append(
            "Ordonnance archivée : vérifier pourquoi elle apparaît encore dans les urgences."
        )

    for rel in data["related"]:
        if "cycle" in rel["model"].lower() and rel["count"] > 0:
            for item in rel["items"]:
                item_status = str(item.get("status", "")).lower()
                if "received" in item_status or "reçu" in item_status:
                    data["anomalies"].append(
                        f"Cycle encore en statut {item.get('status')} pour une ordonnance potentiellement archivée."
                    )
'''

new = '''    integrity_results = run_integrity_for_prescription(prescription)
    score = integrity_score(integrity_results)

    data = {
        "generated_at": NOW,
        "prescription_id": prescription_id,
        "prescription": obj_to_dict(prescription),
        "related": get_related_objects(prescription),
        "integrity": {
            "score": score,
            "results": integrity_results,
        },
        "anomalies": [
            r.get("message")
            for r in integrity_results
            if r.get("severity") in {"ERROR", "WARNING"}
        ],
    }
'''

if old not in text:
    print("❌ Bloc anomalies ancien introuvable.")
    sys.exit(1)

text = text.replace(old, new)

old_md = '''    md.append("")
    md.append("## Anomalies détectées")
    if data["anomalies"]:
        for a in data["anomalies"]:
            md.append(f"- ⚠️ {a}")
    else:
        md.append("- Aucune anomalie automatique détectée.")
'''

new_md = '''    md.append("")
    md.append("## Integrity Score")
    md.append(f"**Score : {data['integrity']['score']} %**")

    md.append("")
    md.append("## Résultats Integrity")
    if data["integrity"]["results"]:
        for r in data["integrity"]["results"]:
            md.append(f"### {r.get('code')} - {r.get('severity')}")
            md.append(f"- Message : {r.get('message')}")
            md.append(f"- Objet : {r.get('object')}")
            md.append(f"- Suggestion : {r.get('suggestion')}")
            md.append("")
    else:
        md.append("- Aucun problème détecté.")

    md.append("")
    md.append("## Anomalies détectées")
    if data["anomalies"]:
        for a in data["anomalies"]:
            md.append(f"- ⚠️ {a}")
    else:
        md.append("- Aucune anomalie automatique détectée.")
'''

if old_md not in text:
    print("❌ Bloc Markdown anomalies introuvable.")
    sys.exit(1)

text = text.replace(old_md, new_md)

old_console = '''    print("Anomalies :")
    if data["anomalies"]:
        for a in data["anomalies"]:
            print("⚠️", a)
    else:
        print("✅ Aucune anomalie automatique détectée.")
'''

new_console = '''    print(f"Integrity Score : {data['integrity']['score']} %")
    print()
    print("Résultats Integrity :")
    if data["integrity"]["results"]:
        for r in data["integrity"]["results"]:
            print(f"{r.get('severity')} {r.get('code')} - {r.get('message')}")
            print(f"   Suggestion : {r.get('suggestion')}")
    else:
        print("✅ Aucun problème détecté.")
'''

if old_console not in text:
    print("❌ Bloc console anomalies introuvable.")
    sys.exit(1)

text = text.replace(old_console, new_console)

inspector.write_text(text, encoding="utf-8")

py_compile.compile(str(inspector), doraise=True)
print("✅ Syntaxe Inspector OK")

log_file = BASE_DIR / "scripts" / "v10" / "migrations.log"
with log_file.open("a", encoding="utf-8") as f:
    f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 013_inspector_integrity | OK\n")

print("=" * 70)
print("✅ SCRIPT 013 TERMINÉ")
print("Inspector branché sur core_integrity.")
print("Test : python scripts/v10/011_inspector.py 17")
print("=" * 70)
