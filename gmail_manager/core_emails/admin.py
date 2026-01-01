# core_emails/admin.py
from django.contrib import admin

from .models import (
    Prescription,
    PrescriptionStatusHistory,
    PrescriptionType,
)
from .models_assignment import PrescriptionAssignment


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "type",          # V3
        "sender_type",
        "received_at",
        "updated_at",
    )

    list_filter = (
        "status",
        "type",          # V3
        "sender_type",
        "received_at",
    )

    ordering = ("-received_at",)

    readonly_fields = (
        "received_at",
        "updated_at",
    )

    fieldsets = (
        (None, {
            "fields": (
                "status",
                "type",      # V3
                "sender_type",
                "patient",
                "created_by",
            )
        }),
        ("Traçabilité", {
            "fields": (
                "received_at",
                "updated_at",
            )
        }),
    )


@admin.register(PrescriptionStatusHistory)
class PrescriptionStatusHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "prescription",
        "old_status",
        "new_status",
        "changed_by",
        "changed_at",
    )

    ordering = ("-changed_at",)

    readonly_fields = (
        "changed_at",
    )


@admin.register(PrescriptionAssignment)
class PrescriptionAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "prescription",
        "nurse",
        "patient",
        "assigned_at",
    )

    ordering = ("-assigned_at",)

    autocomplete_fields = (
        "nurse",
        "patient",
    )

    readonly_fields = (
        "assigned_at",
    )
