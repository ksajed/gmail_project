# gmail_manager/core_emails/emailing.py
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

from core_emails.models import PrescriptionStatus

def send_status_email_to(*, to_email: str, prescription, old_status, new_status, user, recipient_role: str = "patient"):
    """
    Envoie un email de statut à un destinataire explicite (patient ou infirmier).
    Réutilise les mêmes templates que le patient (statuts).
    """
    if not to_email:
        return

    template_map = {

        # Réception
        PrescriptionStatus.RECEIVED.value: "emails/status_received.html",

        # En cours
        PrescriptionStatus.IN_PROGRESS.value: "emails/status_in_progress.html",

        # Prête / délivrée
        PrescriptionStatus.READY.value: "emails/status_validated.html",
        PrescriptionStatus.DELIVERED.value: "emails/status_delivered.html",

        # Bloquée / rejet
        PrescriptionStatus.BLOCKED.value: "emails/status_rejected.html",

        # Fin de vie
        PrescriptionStatus.ARCHIVED.value: "emails/status_archived.html",

    }

    template_name = template_map.get(new_status)
    if not template_name:
        return

    nice_status = new_status.replace("_", " ").title()
    if recipient_role == "nurse":
        subject = f"Ordonnance — Statut mis à jour ({nice_status})"
        text_content = f"Le statut de l’ordonnance a été mis à jour : {nice_status}"
    else:
        subject = f"Ordonnance — {nice_status}"
        text_content = f"Le statut de votre ordonnance est maintenant : {nice_status}"

    context = {
        "prescription": prescription,
        "old_status": old_status,
        "new_status": new_status,
        "recipient_role": recipient_role,
    }

    html_content = render_to_string(template_name, context)

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send()





def send_status_email(*, prescription, old_status, new_status, user):
    if not prescription.patient or not prescription.patient.email:
        return
    return send_status_email_to(
        to_email=prescription.patient.email,
        prescription=prescription,
        old_status=old_status,
        new_status=new_status,
        user=user,
        recipient_role="patient",
    )


    template_map = {
        
         # Réception
      PrescriptionStatus.RECEIVED.value: "emails/status_received.html",

    # En cours
    PrescriptionStatus.IN_PROGRESS.value: "emails/status_in_progress.html",

    # Prête / délivrée
    PrescriptionStatus.READY.value: "emails/status_validated.html",
    PrescriptionStatus.DELIVERED.value: "emails/status_delivered.html",

    # Bloquée / rejet
    PrescriptionStatus.BLOCKED.value: "emails/status_rejected.html",

    # Fin de vie
    PrescriptionStatus.ARCHIVED.value: "emails/status_archived.html",
        
    }

    template_name = template_map.get(new_status)
    if not template_name:
        return

    subject = f"Ordonnance — {new_status.replace('_', ' ').title()}"

    context = {
        "prescription": prescription,
        "old_status": old_status,
        "new_status": new_status,
    }

    html_content = render_to_string(template_name, context)
    text_content = f"Le statut de votre ordonnance est maintenant : {new_status}"

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[prescription.patient.email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send()
