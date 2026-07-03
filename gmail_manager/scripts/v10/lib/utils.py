from pathlib import Path
import sys

def get_base_dir():
    return Path.cwd()

def check_project(base_dir):
    required = ["manage.py", "core_emails", "core_adminconsole"]
    missing = [item for item in required if not (Path(base_dir) / item).exists()]
    return missing

def stop_if_not_project(base_dir):
    missing = check_project(base_dir)
    if missing:
        print("❌ Projet ORDO non détecté.")
        print("Éléments manquants :")
        for item in missing:
            print(" -", item)
        sys.exit(1)

def print_header(title):
    print("=" * 70)
    print(title)
    print("=" * 70)
