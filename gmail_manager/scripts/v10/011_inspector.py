from pathlib import Path
from datetime import datetime
import os
import sys
import json

BASE_DIR = Path.cwd()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gmail_manager.settings")

import django
django.setup()

from django.apps import apps
from core_integrity.runner import run_integrity_for_prescription, integrity_score

NOW = datetime.now().strftime("%Y%m%d_%H%M%S")


def find_model(name):
    for model in apps.get_models():
        if model.__name__.lower() == name.lower():
            return model
    return None


def obj_to_dict(obj):
    data = {}
    for field in obj._meta.fields:
        try:
            data[field.name] = str(getattr(obj, field.name))
        except Exception:
            data[field.name] = None
    return data


def get_related_objects(obj):
    related = []
    for rel in obj._meta.related_objects:
        accessor = rel.get_accessor_name()
        try:
            manager = getattr(obj, accessor)
            items = list(manager.all())
            related.append({
                "accessor": accessor,
                "model": rel.related_model.__name__,
                "count": len(items),
                "items": [obj_to_dict(x) for x in items[:50]],
            })
        except Exception:
            pass
    return related


def main():
    prescription_id = int(sys.argv[1]) if len(sys.argv) > 1 else 17

    print("=" * 70)
    print(f"ORDO V10 - INSPECTOR ORDONNANCE {prescription_id}")
    print("=" * 70)

    Prescription = find_model("Prescription")

    if not Prescription:
        print("❌ Modèle Prescription introuvable.")
        sys.exit(1)

    try:
        prescription = Prescription.objects.get(pk=prescription_id)
    except Exception as e:
        print(f"❌ Ordonnance {prescription_id} introuvable :", e)
        sys.exit(1)

    report_dir = BASE_DIR / "scripts" / "v10" / "reports" / f"{NOW}_inspection_ordonnance_{prescription_id}"
    report_dir.mkdir(parents=True, exist_ok=True)

    integrity_results = run_integrity_for_prescription(prescription)
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

    json_path = report_dir / f"inspection_{prescription_id}.json"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    md = []
    md.append(f"# ORDO Inspector - Ordonnance {prescription_id}")
    md.append("")
    md.append(f"Date : {NOW}")
    md.append("")
    md.append("## Prescription")
    for k, v in data["prescription"].items():
        md.append(f"- **{k}** : {v}")

    md.append("")
    md.append("## Objets liés")
    for rel in data["related"]:
        md.append(f"### {rel['model']} via `{rel['accessor']}`")
        md.append(f"Nombre : {rel['count']}")
        md.append("")
        for item in rel["items"][:10]:
            md.append("```")
            for k, v in item.items():
                md.append(f"{k}: {v}")
            md.append("```")
            md.append("")

    md.append("")
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

    md_path = report_dir / f"inspection_{prescription_id}.md"
    md_path.write_text("\n".join(md), encoding="utf-8")

    print(f"✅ Rapport Markdown : {md_path}")
    print(f"✅ Rapport JSON : {json_path}")
    print()
    print(f"Integrity Score : {data['integrity']['score']} %")
    print()
    print("Résultats Integrity :")
    if data["integrity"]["results"]:
        for r in data["integrity"]["results"]:
            print(f"{r.get('severity')} {r.get('code')} - {r.get('message')}")
            print(f"   Suggestion : {r.get('suggestion')}")
    else:
        print("✅ Aucun problème détecté.")
    print("=" * 70)


if __name__ == "__main__":
    main()
