from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    PrescriptionAttachment,
    PrescriptionAttachmentAccess,
)


@admin.register(PrescriptionAttachment)
class PrescriptionAttachmentAdmin(admin.ModelAdmin):
    """
    Admin des pièces jointes d'ordonnance.

    - 👁️ Voir : ouvre le VIEWER HTML sécurisé (PDF / image + impression)
    - ⬇️ Télécharger : téléchargement forcé
    - AUCUN accès direct aux fichiers médias
    """

    # Colonnes visibles dans la liste
    list_display = (
        "original_filename",
        "prescription",
        "uploaded_at",
        "secure_links",
    )

    # Recherche
    search_fields = (
    "prescription__id",
    "original_filename",
)

    # Tri
    ordering = ("-uploaded_at",)

    def secure_links(self, obj):
        """
        Génère les liens sécurisés par ligne :

        - 👁️ Voir :
          → ouvre une NOUVELLE FENÊTRE
          → page viewer HTML
          → PDF / image affiché
          → bouton 🖨️ Imprimer

        - ⬇️ Télécharger :
          → téléchargement direct
        """

        viewer_url = reverse(
            "attachment_viewer",
            args=[obj.id]
        )

        download_url = reverse(
            "download_attachment",
            args=[obj.id]
        )

        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">'
            '👁️ Voir</a> | '
            '<a href="{}">⬇️ Télécharger</a>',
            viewer_url,
            download_url,
        )

    secure_links.short_description = "Accès sécurisé"


@admin.register(PrescriptionAttachmentAccess)
class PrescriptionAttachmentAccessAdmin(admin.ModelAdmin):
    """
    Audit des accès aux fichiers d'ordonnances.

    - VIEW : visualisation (viewer / stream)
    - DOWNLOAD : téléchargement
    """

    list_display = (
        "attachment",
        "action",
        "accessed_by",
        "accessed_at",
    )

    list_filter = (
        "action",
        "accessed_at",
    )

    ordering = ("-accessed_at",)
