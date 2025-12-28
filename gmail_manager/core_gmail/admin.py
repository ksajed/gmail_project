from django.contrib import admin
from .models import GmailMessage


@admin.register(GmailMessage)
class GmailMessageAdmin(admin.ModelAdmin):
    """
    Emails Gmail déjà traités (anti-doublon).
    """

    list_display = (
        "subject",
        "from_email",
        "received_at",
        "processed_at",
    )

    search_fields = (
        "subject",
        "from_email",
        "message_id",
    )

    ordering = ("-processed_at",)
