from pathlib import Path
from django.core.management.base import BaseCommand

from core_audit.scanner import count_models
from core_audit.integrity_audit import audit_prescriptions
from core_audit.report import write_audit_report
from core_anomalies.sync import sync_anomalies


class Command(BaseCommand):
    help = "ORDO V11 - Audit global lecture seule"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **options):
        base_dir = Path.cwd()
        limit = options.get("limit")

        self.stdout.write("🔎 ORDO Audit global...")

        model_counts = count_models()
        integrity_report = audit_prescriptions(limit=limit)
        sync_result = sync_anomalies(limit=limit)

        report_dir, md_path, json_path = write_audit_report(
            base_dir,
            model_counts,
            integrity_report,
        )

        self.stdout.write(self.style.SUCCESS("✅ Audit terminé"))
        self.stdout.write(f"📁 Dossier : {report_dir}")
        self.stdout.write(f"📄 Markdown : {md_path}")
        self.stdout.write(f"🧠 JSON : {json_path}")
        self.stdout.write(f"⚠️ Anomalies : {integrity_report.get('anomalies_count')}")
        self.stdout.write(f"🔁 Synchronisation anomalies : {sync_result}")
