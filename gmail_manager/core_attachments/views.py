# core_attachments/views.py
import mimetypes

from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin

from .models import (
    PrescriptionAttachment,
    PrescriptionAttachmentAccess,
)


# ============================================================
# STREAM SÉCURISÉ — VISUALISATION (PDF / IMAGE / AUTRE)
# ============================================================

@login_required
@xframe_options_sameorigin
def view_attachment(request, attachment_id):
    """
    Vue sécurisée pour STREAMER un fichier d'ordonnance.

    - Autorise l'affichage dans <object> / <iframe> (SAMEORIGIN)
    - Utilisée par le viewer HTML
    - Aucun accès direct aux fichiers médias
    - Audit VIEW enregistré
    """

    attachment = get_object_or_404(
        PrescriptionAttachment,
        id=attachment_id
    )

    # ✅ CORRECTION MINIMALE :
    # Forcer le Content-Type pour les PDF afin d'éviter
    # le téléchargement automatique dans le navigateur.
    if attachment.is_pdf:
        content_type = "application/pdf"
    else:
        content_type, _ = mimetypes.guess_type(
            attachment.file.path
        )
        if not content_type:
            content_type = "application/octet-stream"

    # 🕒 Audit VIEW
    PrescriptionAttachmentAccess.objects.create(
        attachment=attachment,
        accessed_by=request.user,
        action="VIEW",
    )

    response = FileResponse(
        open(attachment.file.path, "rb"),
        content_type=content_type
    )

    # inline = affichage navigateur (PDF / image)
    response["Content-Disposition"] = (
        f'inline; filename="{attachment.original_filename}"'
    )

    return response


# ============================================================
# STREAM SÉCURISÉ — TÉLÉCHARGEMENT
# ============================================================

@login_required
def download_attachment(request, attachment_id):
    """
    Vue sécurisée pour TÉLÉCHARGER un fichier d'ordonnance.

    - Téléchargement forcé
    - Audit DOWNLOAD enregistré
    """

    attachment = get_object_or_404(
        PrescriptionAttachment,
        id=attachment_id
    )

    content_type, _ = mimetypes.guess_type(
        attachment.file.path
    )

    if not content_type:
        content_type = "application/octet-stream"

    # 🕒 Audit DOWNLOAD
    PrescriptionAttachmentAccess.objects.create(
        attachment=attachment,
        accessed_by=request.user,
        action="DOWNLOAD",
    )

    response = FileResponse(
        open(attachment.file.path, "rb"),
        content_type=content_type
    )

    response["Content-Disposition"] = (
        f'attachment; filename="{attachment.original_filename}"'
    )

    return response


# ============================================================
# VIEWER HTML — VISUALISATION + IMPRESSION
# ============================================================

@login_required
def attachment_viewer(request, attachment_id):
    """
    Page HTML sécurisée de visualisation d'une ordonnance.

    - PDF affiché via <object>
    - Image affichée via <img>
    - Autres formats via fallback
    - Impression navigateur possible
    - AUCUN audit ici (fait dans view_attachment)
    """

    attachment = get_object_or_404(
        PrescriptionAttachment,
        id=attachment_id
    )

    context = {
        "attachment": attachment,
        "is_pdf": attachment.is_pdf,
        "is_image": attachment.is_image,
        # Flux sécurisé utilisé par <object> / <img>
        "stream_url": reverse(
            "core_attachments:view_attachment",
            args=[attachment.id]
        ),
    }

    return render(
        request,
        "core_attachments/viewer.html",
        context
    )
