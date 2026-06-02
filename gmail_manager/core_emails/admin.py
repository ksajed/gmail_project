# core_emails/admin.py
from django.contrib import admin

from .models import (
    Prescription,
    PrescriptionStatusHistory,
    PrescriptionRenewalInfo,  # ✅ V7
    RenewalSettings,
    RenewalNotificationRule,
    RenewalNotificationTemplate,
    Holiday,
)
from .models_assignment import PrescriptionAssignment


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "type",
        "sender_type",
        "patient",
        "established_at",   # ✅ V7 (visible direct)
        "received_at",
        "updated_at",
    )

    list_filter = (
        "status",
        "type",
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
                "type",
                "sender_type",
                "patient",
                "established_at",   # ✅ V7 (saisie date médecin)
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


# ✅ V7 — Admin RenewalInfo
@admin.register(PrescriptionRenewalInfo)
class PrescriptionRenewalInfoAdmin(admin.ModelAdmin):
    list_display = (
        "prescription",
        "renewal_times",
        "period_days",
        "doctor_email",
        "doctor_email_sent_at",
    )
    search_fields = ("prescription__id", "doctor_email", "doctor_name")
    ordering = ("-prescription__received_at",)
    readonly_fields = (
        "doctor_email_sent_at",
        "reminder_5_patient_email_sent_at",
        "reminder_5_patient_sms_sent_at",
        "reminder_3_patient_email_sent_at",
        "reminder_3_patient_sms_sent_at",
    )
    fieldsets = (
        (None, {
            "fields": (
                "prescription",
                "renewal_times",
                "period_days",
            )
        }),
        ("Contact médecin", {
            "fields": (
                "doctor_email",
                "doctor_name",
            )
        }),
        ("Statut des envois", {
            "fields": (
                "doctor_email_sent_at",
                "reminder_5_patient_email_sent_at",
                "reminder_5_patient_sms_sent_at",
                "reminder_3_patient_email_sent_at",
                "reminder_3_patient_sms_sent_at",
            )
        }),
    )


# ============================================================
# ORDO V9 - Administration du paramétrage Renouvellements
# Ajout non destructif : aucun impact sur le moteur V8.
# ============================================================

@admin.register(RenewalSettings)
class RenewalSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "pharmacy_name",
        "phone",
        "email",
        "opening_time",
        "closing_time",
        "updated_at",
    )
    search_fields = (
        "pharmacy_name",
        "phone",
        "email",
    )
    ordering = ("pharmacy_name",)


@admin.register(RenewalNotificationRule)
class RenewalNotificationRuleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "days_before",
        "send_sms",
        "send_email",
        "active",
        "sort_order",
        "updated_at",
    )
    list_filter = (
        "active",
        "send_sms",
        "send_email",
    )
    search_fields = (
        "name",
    )
    ordering = (
        "sort_order",
        "-days_before",
        "name",
    )


@admin.register(RenewalNotificationTemplate)
class RenewalNotificationTemplateAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "channel",
        "active",
        "updated_at",
    )
    list_filter = (
        "channel",
        "active",
    )
    search_fields = (
        "name",
        "subject",
        "body",
    )
    ordering = (
        "channel",
        "name",
    )


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "date",
        "active",
        "created_at",
    )
    list_filter = (
        "active",
        "date",
    )
    search_fields = (
        "name",
    )
    ordering = (
        "date",
    )

