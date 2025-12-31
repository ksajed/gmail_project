# gmail_manager/core_notifications/admin.py
from django.contrib import admin, messages
from .models import Notification


@admin.action(description="✅ Marquer comme LU")
def mark_as_read(modeladmin, request, queryset):
    """
    Marque les notifications sélectionnées comme lues.
    """
    count = queryset.update(is_read=True)

    if count == 0:
        modeladmin.message_user(
            request,
            "Aucune notification sélectionnée.",
            level=messages.WARNING,
        )
    else:
        modeladmin.message_user(
            request,
            f"{count} notification(s) marquée(s) comme LU.",
            level=messages.SUCCESS,
        )


@admin.action(description="🔴 Marquer comme NON LU")
def mark_as_unread(modeladmin, request, queryset):
    """
    Marque les notifications sélectionnées comme non lues.
    """
    count = queryset.update(is_read=False)

    if count == 0:
        modeladmin.message_user(
            request,
            "Aucune notification sélectionnée.",
            level=messages.WARNING,
        )
    else:
        modeladmin.message_user(
            request,
            f"{count} notification(s) marquée(s) comme NON LU.",
            level=messages.SUCCESS,
        )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """
    Admin des notifications internes (pharmacie).
    Gestion par ACTIONS UNIQUEMENT.
    """

    list_display = (
        "title",
        "recipient",
        "is_read",
        "created_at",
    )

    list_display_links = ("title",)

    list_filter = ("is_read", "created_at", "recipient")

    search_fields = (
        "title",
        "message",
        "recipient__username",
        "recipient__email",
    )

    ordering = ("-created_at",)

    # ✅ ACTIONS SEULEMENT
    actions = (
        mark_as_read,
        mark_as_unread,
    )

    # ❌ PAS D'ÉDITION DIRECTE
    list_editable = ()
