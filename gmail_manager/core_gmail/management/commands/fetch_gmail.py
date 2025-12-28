from django.core.management.base import BaseCommand
from core_gmail.services import fetch_new_gmail_messages


class Command(BaseCommand):
    help = "Récupère les nouveaux emails Gmail"

    def handle(self, *args, **options):
        fetch_new_gmail_messages()
        self.stdout.write(
            self.style.SUCCESS("Synchronisation Gmail terminée.")
        )
