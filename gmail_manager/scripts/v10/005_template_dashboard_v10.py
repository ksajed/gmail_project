from pathlib import Path
from datetime import datetime
import shutil
import sys

BASE_DIR = Path.cwd()
NOW = datetime.now().strftime("%Y%m%d_%H%M%S")

print("=" * 70)
print("ORDO V10 - 005 TEMPLATE DASHBOARD V10")
print("=" * 70)

required = ["manage.py", "core_emails", "scripts/v10"]
missing = [x for x in required if not (BASE_DIR / x).exists()]
if missing:
    print("❌ Projet ORDO non détecté :", missing)
    sys.exit(1)

template_dir = BASE_DIR / "core_emails" / "templates" / "core_emails"
template_dir.mkdir(parents=True, exist_ok=True)

target = template_dir / "renewals_dashboard_v10.html"

backup_dir = BASE_DIR / "backups" / "ordo_v10" / f"{NOW}_005_template_dashboard_v10"
backup_dir.mkdir(parents=True, exist_ok=True)

if target.exists():
    backup_target = backup_dir / "core_emails" / "templates" / "core_emails" / "renewals_dashboard_v10.html"
    backup_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, backup_target)
    print(f"📦 Backup créé : {backup_target}")

content = r'''
{% extends "base.html" %}

{% block content %}

<div style="padding: 24px;">

  <h1>Renouvellements</h1>
  <p style="font-size: 18px;">ORDO travaille pour vous.</p>

  <hr>

  <h2>Travail automatique</h2>

  <div style="display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px;">

    <div style="border: 1px solid #ddd; border-radius: 8px; padding: 16px; min-width: 160px;">
      <div style="font-size: 32px; font-weight: bold;">{{ today_activity.sms_sent }}</div>
      <div>SMS envoyés</div>
    </div>

    <div style="border: 1px solid #ddd; border-radius: 8px; padding: 16px; min-width: 160px;">
      <div style="font-size: 32px; font-weight: bold;">{{ today_activity.emails_sent }}</div>
      <div>Emails envoyés</div>
    </div>

    <div style="border: 1px solid #ddd; border-radius: 8px; padding: 16px; min-width: 160px;">
      <div style="font-size: 32px; font-weight: bold;">{{ today_activity.notifications_created }}</div>
      <div>Notifications créées</div>
    </div>

    <div style="border: 1px solid #ddd; border-radius: 8px; padding: 16px; min-width: 160px;">
      <div style="font-size: 32px; font-weight: bold;">{{ today_activity.cycles_created }}</div>
      <div>Cycles créés</div>
    </div>

  </div>

  <h2>Votre travail</h2>

  <div style="display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px;">

    <div style="border: 1px solid #ddd; border-radius: 8px; padding: 16px; min-width: 200px;">
      <div style="font-size: 32px; font-weight: bold;">{{ pharmacist_work.patients_to_call }}</div>
      <div>Patients à appeler</div>
    </div>

    <div style="border: 1px solid #ddd; border-radius: 8px; padding: 16px; min-width: 200px;">
      <div style="font-size: 32px; font-weight: bold;">{{ pharmacist_work.renewals_to_check }}</div>
      <div>Renouvellements à contrôler</div>
    </div>

    <div style="border: 1px solid #ddd; border-radius: 8px; padding: 16px; min-width: 200px;">
      <div style="font-size: 32px; font-weight: bold;">{{ pharmacist_work.urgent_files }}</div>
      <div>Dossiers urgents</div>
    </div>

  </div>

  <h2>Urgences</h2>

  {% for item in sections.urgent %}
    <div style="border-left: 4px solid #900; padding: 12px; margin-bottom: 8px; background: #fff5f5;">
      <strong>{{ item }}</strong>
      <p>Action recommandée : contrôler maintenant.</p>
    </div>
  {% empty %}
    <p>Aucune urgence.</p>
  {% endfor %}

  <h2>Patients à appeler</h2>

  {% for item in sections.overdue %}
    <div style="border-left: 4px solid #c60; padding: 12px; margin-bottom: 8px; background: #fffaf0;">
      <strong>{{ item }}</strong>
      <p>Renouvellement en retard. Action recommandée : appeler le patient.</p>
    </div>
  {% empty %}
    <p>Aucun patient à appeler.</p>
  {% endfor %}

  <h2>À contrôler</h2>

  {% for item in sections.to_check %}
    <div style="border-left: 4px solid #06c; padding: 12px; margin-bottom: 8px; background: #f5f9ff;">
      <strong>{{ item }}</strong>
      <p>Action recommandée : vérifier le renouvellement.</p>
    </div>
  {% empty %}
    <p>Aucun renouvellement à contrôler.</p>
  {% endfor %}

  <hr>

  <p style="font-size: 12px; color: #777;">
    ORDO V10 - Dashboard lecture seule.
    Source moteur : {{ engine_status.source|default:"non détectée" }}
  </p>

</div>

{% endblock %}
'''

target.write_text(content.strip() + "\n", encoding="utf-8")
print(f"✅ Template créé : {target}")

log_file = BASE_DIR / "scripts" / "v10" / "migrations.log"
with log_file.open("a", encoding="utf-8") as f:
    f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 005_template_dashboard_v10 | OK | {target}\n")

print("=" * 70)
print("✅ SCRIPT 005 TERMINÉ")
print("Template Dashboard V10 créé.")
print("=" * 70)
