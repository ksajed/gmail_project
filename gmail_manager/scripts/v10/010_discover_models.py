from pathlib import Path
from datetime import datetime
import os
import sys
import json

BASE_DIR = Path.cwd()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
NOW = datetime.now().strftime("%Y%m%d_%H%M%S")

print("=" * 70)
print("ORDO V10 - 010 DECOUVERTE MODELES DJANGO")
print("=" * 70)

if not (BASE_DIR / "manage.py").exists():
    print("❌ Lance ce script depuis le dossier où se trouve manage.py")
    sys.exit(1)


os.environ["DJANGO_SETTINGS_MODULE"] = "gmail_manager.settings"

try:
    import django
    django.setup()
    print("✅ Settings Django détecté : gmail_manager.settings")
except Exception as e:
    print("❌ Impossible de charger Django :")
    print(repr(e))
    sys.exit(1)



from django.apps import apps

REPORT_DIR = BASE_DIR / "scripts" / "v10" / "reports" / f"{NOW}_models_discovery"
CACHE_DIR = BASE_DIR / "scripts" / "v10" / "cache"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

schema = {
    "generated_at": NOW,
    "models": []
}

md = []
md.append("# ORDO V10 - Découverte des modèles Django\n")

for model in apps.get_models():
    app_label = model._meta.app_label
    model_name = model.__name__

    item = {
        "app": app_label,
        "model": model_name,
        "db_table": model._meta.db_table,
        "fields": [],
        "relations": [],
    }

    md.append(f"## {app_label}.{model_name}")
    md.append(f"Table : `{model._meta.db_table}`\n")

    for field in model._meta.get_fields():
        field_info = {
            "name": field.name,
            "type": field.__class__.__name__,
            "is_relation": field.is_relation,
        }

        if field.is_relation and getattr(field, "related_model", None):
            related = field.related_model
            field_info["related_model"] = f"{related._meta.app_label}.{related.__name__}"
            item["relations"].append(field_info)
            md.append(f"- `{field.name}` → `{field_info['related_model']}` ({field_info['type']})")
        else:
            item["fields"].append(field_info)
            md.append(f"- `{field.name}` ({field_info['type']})")

    schema["models"].append(item)
    md.append("")

json_path = CACHE_DIR / "project_schema.json"
json_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")

report_path = REPORT_DIR / "models_discovery.md"
report_path.write_text("\n".join(md), encoding="utf-8")

log_file = BASE_DIR / "scripts" / "v10" / "migrations.log"
with log_file.open("a", encoding="utf-8") as f:
    f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 010_discover_models | OK | {report_path}\n")

print("✅ Découverte terminée")
print(f"📄 Rapport : {report_path}")
print(f"🧠 JSON : {json_path}")
print("=" * 70)
