from pathlib import Path
from datetime import datetime
import shutil
import py_compile
import subprocess
import sys

BASE_DIR = Path.cwd()
NOW = datetime.now().strftime("%Y%m%d_%H%M%S")

service = BASE_DIR / "core_emails/services_renewal_v10.py"
template = BASE_DIR / "core_emails/templates/core_emails/renewals_dashboard_v10.html"

backup_dir = BASE_DIR / "backups" / "ordo_v10" / f"{NOW}_015_dashboard_integrity_split"
backup_dir.mkdir(parents=True, exist_ok=True)

for p in [service, template]:
    dest = backup_dir / p.relative_to(BASE_DIR)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, dest)
    print(f"📦 Backup : {dest}")

text = service.read_text(encoding="utf-8")

if '"anomalies": []' not in text:
    text = text.replace('"history": [],', '"history": [],\n            "anomalies": [],')

if '"anomalies_count": 0' not in text:
    text = text.replace(
        '"urgent_files": 0,',
        '"urgent_files": 0,\n            "anomalies_count": 0,'
    )

helper = r'''

def _integrity_results_for_item(item):
    try:
        from core_integrity.runner import run_integrity_for_prescription, integrity_score
    except Exception:
        return [], 100

    if not isinstance(item, dict):
        return [], 100

    prescription = item.get("prescription")

    if not prescription:
        return [], 100

    try:
        results = run_integrity_for_prescription(prescription)
        score = integrity_score(results)
        return results, score
    except Exception:
        return [], 100


def _split_integrity(items):
    normal = []
    anomalies = []

    for item in items or []:
        results, score = _integrity_results_for_item(item)

        has_problem = any(
            r.get("severity") in {"ERROR", "WARNING"}
            for r in results
        )

        if has_problem:
            formatted = _format_item(item)
            formatted["integrity_score"] = score
            formatted["integrity_results"] = results
            anomalies.append(formatted)
        else:
            normal.append(item)

    return normal, anomalies
'''

if "def _split_integrity(items):" not in text:
    text = text.replace("def compute_renewals_dashboard_v10():", helper + "\n\ndef compute_renewals_dashboard_v10():")

old = '''    dashboard["sections"]["urgent"] = _format_list(urgent)
    dashboard["sections"]["overdue"] = _format_list(overdue)
    dashboard["sections"]["to_check"] = _format_list(to_check)
    dashboard["sections"]["active"] = _format_list(active)

    dashboard["pharmacist_work"]["patients_to_call"] = _safe_len(overdue)
    dashboard["pharmacist_work"]["renewals_to_check"] = _safe_len(to_check)
    dashboard["pharmacist_work"]["urgent_files"] = _safe_len(urgent)
'''

new = '''    urgent_normal, urgent_anomalies = _split_integrity(urgent)
    overdue_normal, overdue_anomalies = _split_integrity(overdue)
    to_check_normal, to_check_anomalies = _split_integrity(to_check)

    all_anomalies = urgent_anomalies + overdue_anomalies + to_check_anomalies

    dashboard["sections"]["urgent"] = _format_list(urgent_normal)
    dashboard["sections"]["overdue"] = _format_list(overdue_normal)
    dashboard["sections"]["to_check"] = _format_list(to_check_normal)
    dashboard["sections"]["active"] = _format_list(active)
    dashboard["sections"]["anomalies"] = all_anomalies[:20]

    dashboard["pharmacist_work"]["patients_to_call"] = _safe_len(overdue_normal)
    dashboard["pharmacist_work"]["renewals_to_check"] = _safe_len(to_check_normal)
    dashboard["pharmacist_work"]["urgent_files"] = _safe_len(urgent_normal)
    dashboard["pharmacist_work"]["anomalies_count"] = _safe_len(all_anomalies)
'''

if old not in text:
    print("❌ Bloc dashboard sections introuvable.")
    sys.exit(1)

text = text.replace(old, new)
service.write_text(text, encoding="utf-8")

html = template.read_text(encoding="utf-8")

if "Dossiers incohérents" not in html:
    html = html.replace(
        '''
    <div style="border: 1px solid #ddd; border-radius: 8px; padding: 16px; min-width: 200px;">
      <div style="font-size: 32px; font-weight: bold;">{{ pharmacist_work.urgent_files }}</div>
      <div>Dossiers urgents</div>
    </div>
''',
        '''
    <div style="border: 1px solid #ddd; border-radius: 8px; padding: 16px; min-width: 200px;">
      <div style="font-size: 32px; font-weight: bold;">{{ pharmacist_work.urgent_files }}</div>
      <div>Dossiers urgents</div>
    </div>

    <div style="border: 1px solid #b00020; border-radius: 8px; padding: 16px; min-width: 200px; background:#fff5f5;">
      <div style="font-size: 32px; font-weight: bold;">{{ pharmacist_work.anomalies_count }}</div>
      <div>Dossiers incohérents</div>
    </div>
'''
    )

    html = html.replace(
        "<h2>Urgences</h2>",
        '''
<h2>Dossiers incohérents</h2>

{% for item in sections.anomalies %}
  <div style="border-left: 4px solid #b00020; padding: 12px; margin-bottom: 8px; background: #fff5f5;">
    <strong><a href="{{ item.url }}" target="_blank" rel="noopener" style="color:#0a8f3c;text-decoration:none;">{{ item.title }}</a></strong>
    <p>Score intégrité : {{ item.integrity_score }} %</p>

    {% for r in item.integrity_results %}
      <p><strong>{{ r.code }}</strong> — {{ r.message }}</p>
      <p>Suggestion : {{ r.suggestion }}</p>
    {% endfor %}

    <p><a href="{{ item.url }}" target="_blank" rel="noopener" style="display:inline-block;background:#0a8f3c;color:white;padding:8px 12px;border-radius:6px;text-decoration:none;font-weight:bold;">📄 Ouvrir ordonnance</a></p>
  </div>
{% empty %}
  <p>Aucune incohérence détectée.</p>
{% endfor %}

<h2>Urgences normales</h2>
'''
    )

template.write_text(html, encoding="utf-8")

py_compile.compile(str(service), doraise=True)

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

print("✅ SCRIPT 015 TERMINÉ")
print("Dashboard V10 : urgences normales et anomalies séparées.")
