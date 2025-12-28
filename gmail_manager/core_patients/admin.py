from django.contrib import admin
from .models import Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("email", "full_name", "phone_number", "created_at")
    search_fields = ("email", "full_name", "phone_number")
    ordering = ("-created_at",)
