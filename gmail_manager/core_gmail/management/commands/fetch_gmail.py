from django.core.management.base import BaseCommand
from core_gmail.services import fetch_new_gmail_messages


class Command(BaseCommand):
    help = "Récupère les nouveaux emails Gmail"

    def add_arguments(self, parser):
        parser.add_argument("--criteria", default=None, help="IMAP criteria (ex: UNSEEN, X-GM-RAW:newer_than:7d)")
        parser.add_argument("--days", type=int, default=None, help="Shortcut: X-GM-RAW newer_than:<days>d")
        parser.add_argument("--limit", type=int, default=None, help="Limiter le nombre de messages traités (plus récents)")

    def handle(self, *args, **options):
        criteria = options.get("criteria")
        days = options.get("days")
        limit = options.get("limit")

        if days is not None:
            criteria = ("X-GM-RAW", f"newer_than:{int(days)}d")

        # Autorise "X-GM-RAW:<query>" depuis CLI
        if isinstance(criteria, str) and criteria.upper().startswith("X-GM-RAW:"):
            criteria = ("X-GM-RAW", criteria.split(":", 1)[1].strip())

        stats = fetch_new_gmail_messages(search_criteria=criteria, limit=limit)

        self.stdout.write(self.style.SUCCESS(
            "Synchronisation Gmail terminée. "
            f"criteria={stats.get('search_args')} "
            f"candidats={stats.get('candidates')} "
            f"skipped={stats.get('skipped_existing')} "
            f"new={stats.get('created_messages')} "
            f"presc={stats.get('created_prescriptions')} "
            f"pj={stats.get('saved_attachments')} "
            f"durée={stats.get('duration_s')}s"
        ))
