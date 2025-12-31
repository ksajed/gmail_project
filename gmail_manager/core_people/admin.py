from django.contrib import admin
from .models import Person


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    """
    Admin des personnes externes (organisationnel).
    """

    list_display = (
        "id",
        "role",
        "first_name",
        "last_name",
        "email",
    )

    list_filter = (
        "role",
    )

    search_fields = (
        "first_name",
        "last_name",
        "email",
    )

    ordering = (
        "last_name",
        "first_name",
    )
