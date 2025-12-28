from django.contrib import admin
from .models import Prescription, PrescriptionStatusHistory


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    """
    Admin des ordonnances (pharmacie unique).
    """

    list_display = (
        "id",
        "status",
        "received_at",
        "updated_at",
    )

    list_filter = (
        "status",
        "received_at",
    )

    ordering = ("-received_at",)

    readonly_fields = (
        "received_at",
        "updated_at",
    )


@admin.register(PrescriptionStatusHistory)
class PrescriptionStatusHistoryAdmin(admin.ModelAdmin):
    """
    Historique légal des statuts d’ordonnance.
    """

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
