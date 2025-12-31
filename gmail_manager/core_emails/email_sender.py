# gmail_manager/core_emails/email_sender.py
from django.conf import settings
from django.core.mail import send_mail


def send_ack_email(*, to_email: str, prescription_id: int):
    """
    Envoie un accusé de réception automatique après réception d’ordonnance.
    """

    subject = "Ordonnance reçue – en cours de traitement"
    message = (
        "Bonjour,\n\n"
        "Votre ordonnance a bien été reçue par la pharmacie.\n"
        "Elle est actuellement en cours de traitement.\n\n"
        f"Référence : ORD-{prescription_id}\n\n"
        "Merci de ne pas répondre à ce message.\n"
        "— Pharmacie"
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[to_email],
        fail_silently=False,
    )
