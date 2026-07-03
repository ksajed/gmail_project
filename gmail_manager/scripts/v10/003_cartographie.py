from pathlib import Path
from datetime import datetime
import ast
import json
import sys

BASE_DIR = Path.cwd()
NOW = datetime.now().strftime("%Y%m%d_%H%M%S")

REPORT_DIR = BASE_DIR / "scripts" / "v10" / "reports" / f"{NOW}_cartographie_renewals"
CACHE_DIR = BASE_DIR / "scripts" / "v10" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

KEYWORDS = [
    "renewal", "renewals", "renouvel",
    "cycle", "notification", "sms",
    "email", "prescription"
]

IGNORED = {"venv", ".git", "__pycache__", "backups", "node_modules", ".pytest_cache"}

def is_ignored(path):
    return any(part in IGNORED for part in path.parts)

def rel(path):
    return str(path.relative_to(BASE_DIR))

def write_report(name, content):
    path = REPORT_DIR / name
    path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"✅ Rapport : {path}")

def contains_keyword(path):
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    return any(k in text or k in path.name.lower() for k in KEYWORDS)

def main():
    print("=" * 70)
    print("ORDO V10 - 003 CARTOGRAPHIE RENOUVELLEMENTS")
    print("=" * 70)

    required = ["manage.py", "core_emails", "core_adminconsole", "scripts/v10"]
    missing = [x for x in required if not (BASE_DIR / x).exists()]
    if missing:
        print("❌ Projet ORDO non détecté.")
        print(missing)
        sys.exit(1)

    py_files = [p for p in BASE_DIR.rglob("*.py") if not is_ignored(p)]
    html_files = [p for p in BASE_DIR.rglob("*.html") if not is_ignored(p)]

    data = {
        "generated_at": NOW,
        "renewals": {
            "python_files": [],
            "templates": [],
            "urls": [],
            "views": [],
            "services": [],
            "models": [],
            "management_commands": [],
            "renders": [],
            "imports": [],
        }
    }

    for path in py_files:
        if not contains_keyword(path):
            continue

        r = rel(path)
        data["renewals"]["python_files"].append(r)

        if path.name == "models.py":
            data["renewals"]["models"].append(r)

        if "views" in path.name:
            data["renewals"]["views"].append(r)

        if "service" in path.name.lower() or "renewal" in path.name.lower():
            data["renewals"]["services"].append(r)

        if "management" in path.parts and "commands" in path.parts:
            data["renewals"]["management_commands"].append(r)

        text = path.read_text(encoding="utf-8", errors="ignore")

        if path.name == "urls.py":
            for line in text.splitlines():
                if "path(" in line or "re_path(" in line:
                    if any(k in line.lower() for k in KEYWORDS):
                        data["renewals"]["urls"].append({
                            "file": r,
                            "line": line.strip()
                        })

        try:
            tree = ast.parse(text)
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                try:
                    data["renewals"]["imports"].append({
                        "file": r,
                        "import": ast.unparse(node)
                    })
                except Exception:
                    pass

            if isinstance(node, ast.Call):
                try:
                    call = ast.unparse(node)
                except Exception:
                    call = ""

                if "render(" in call:
                    data["renewals"]["renders"].append({
                        "file": r,
                        "call": call[:300]
                    })

    for path in html_files:
        if contains_keyword(path):
            data["renewals"]["templates"].append(rel(path))

    json_path = CACHE_DIR / "project_map.json"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    md = []
    md.append("# ORDO V10 - Cartographie Renouvellements")
    md.append("")
    md.append(f"Date : {NOW}")
    md.append("")
    md.append("## Fichiers Python")
    for x in data["renewals"]["python_files"]:
        md.append(f"- `{x}`")
    md.append("")
    md.append("## Vues")
    for x in data["renewals"]["views"]:
        md.append(f"- `{x}`")
    md.append("")
    md.append("## Services")
    for x in data["renewals"]["services"]:
        md.append(f"- `{x}`")
    md.append("")
    md.append("## Templates")
    for x in data["renewals"]["templates"]:
        md.append(f"- `{x}`")
    md.append("")
    md.append("## URLs")
    for x in data["renewals"]["urls"]:
        md.append(f"- `{x['file']}` : `{x['line']}`")
    md.append("")
    md.append("## Render détectés")
    for x in data["renewals"]["renders"]:
        md.append(f"- `{x['file']}` : `{x['call']}`")
    md.append("")
    md.append("## Commandes management")
    for x in data["renewals"]["management_commands"]:
        md.append(f"- `{x}`")

    write_report("cartographie_renewals.md", "\n".join(md))

    impact = """
# ORDO V10 - Impact recommandé

## Ne pas modifier maintenant

- `core_emails/models.py`
- moteur V9
- commandes management existantes
- règles de calcul existantes

## Créer en priorité

- `core_emails/services_renewal_v10.py`
- `core_emails/templates/core_emails/renewals_dashboard_v10.html`

## Modifier plus tard avec backup

- vue dashboard actuelle dans `core_emails/views.py`
"""
    write_report("impact_renewals.md", impact)

    html = f"""
<!doctype html>
<html>
<head><meta charset="utf-8"><title>ORDO V10 Cartographie</title></head>
<body>
<h1>ORDO V10 - Cartographie Renouvellements</h1>
<p>Date : {NOW}</p>
<ul>
<li>Fichiers Python : {len(data['renewals']['python_files'])}</li>
<li>Vues : {len(data['renewals']['views'])}</li>
<li>Services : {len(data['renewals']['services'])}</li>
<li>Templates : {len(data['renewals']['templates'])}</li>
<li>URLs : {len(data['renewals']['urls'])}</li>
</ul>
<p>JSON central : scripts/v10/cache/project_map.json</p>
</body>
</html>
"""
    write_report("index.html", html)

    log_file = BASE_DIR / "scripts" / "v10" / "migrations.log"
    with log_file.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 003_cartographie | OK | {REPORT_DIR}\n")

    print("=" * 70)
    print("✅ SCRIPT 003 TERMINÉ")
    print(f"JSON : {json_path}")
    print(f"Rapports : {REPORT_DIR}")
    print("=" * 70)

if __name__ == "__main__":
    main()
