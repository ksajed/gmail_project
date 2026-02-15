from __future__ import annotations

from unittest.mock import patch
from django.test import TestCase, override_settings
from django.utils import timezone

from core_patients.models import Patient
from core_emails.models import (
    Prescription,
    PrescriptionStatus,
    PrescriptionType,
    PrescriptionNotificationSettings,
)

# IMPORTANT:
# - send_mail est importé dans core_emails/services_notifications.py
SEND_MAIL_PATCH_PATH = "core_emails.services_notifications.send_mail"

# - on évite le réseau OVH : send_sms_logged appelle le backend OVH qui fait _request()
OVH_REQUEST_PATCH_PATH = "core_notifications.backends.ovh.OvhSmsBackend._request"


@override_settings(
    DEFAULT_FROM_EMAIL="no-reply@ordo.local",
    SERVER_EMAIL="server@ordo.local",
)
class NotificationsGeneralTests(TestCase):
    """
    Test général : notifications respectent les règles demandées.
    - Email: uniquement au patient (jamais à l'admin / adresses internes)
    - SMS: via send_sms_logged (backend OVH mocké), RGPD-safe (pas d'email, pas de données sensibles)
    - Channels: NONE / SMS / EMAIL / BOTH
    """

    def setUp(self):
        self.admin_email = "khalidsajed19755@gmail.com"  # la mauvaise adresse qui ne doit JAMAIS recevoir

        self.patient = Patient.objects.create(
            full_name="Patient Test",
            email="patient@example.com",
            phone_number="06 12 34 56 78",
        )

        self.rx = Prescription.objects.create(
            patient=self.patient,
            status=PrescriptionStatus.RECEIVED,
            type=PrescriptionType.INCOMPLETE,  # type existant (INCOMPLETE est créé par core_gmail)
        )

        self.ns = PrescriptionNotificationSettings.objects.create(
            prescription=self.rx,
            patient_channel="NONE",
            nurse_channel="NONE",
            free_text_message="Votre ordonnance est en cours de traitement.",
        )

    def _assert_email_only_to_patient(self, mock_send_mail):
        """
        Vérifie qu’aucun email ne part vers l’admin ou vers des adresses internes.
        """
        self.assertTrue(mock_send_mail.called, "send_mail doit être appelé quand channel EMAIL/BOTH")
        _, kwargs = mock_send_mail.call_args
        recipient_list = kwargs.get("recipient_list") or []
        self.assertIn(self.patient.email, recipient_list, "Le patient doit recevoir l'email")

        forbidden = {self.admin_email, "no-reply@ordo.local", "server@ordo.local", "smtp-user@ordo.local"}
        self.assertTrue(forbidden.isdisjoint(set(recipient_list)),
                        f"Interdit: email vers {forbidden & set(recipient_list)}")

        # Et surtout: un seul destinataire attendu (patient only)
        self.assertEqual(recipient_list, [self.patient.email], "Email doit être envoyé uniquement au patient")

    def _assert_no_email(self, mock_send_mail):
        self.assertFalse(mock_send_mail.called, "Aucun email ne doit partir quand channel != EMAIL/BOTH")

    def _assert_sms_created_rgpd_safe(self):
        from core_notifications.models import SmsMessage

        self.assertEqual(SmsMessage.objects.count(), 1, "Un SmsMessage doit être créé")
        sms = SmsMessage.objects.latest("id")

        self.assertTrue(sms.recipient_phone.startswith("+33"), "Le téléphone doit être normalisé en E.164 (+33...)")
        txt = sms.rendered_text or ""
        self.assertNotIn("@", txt, "RGPD: pas d'email dans le SMS")
        # on garde une vérif light: pas de mots à risque (à adapter si tu veux)
        risky = ["ordonnance", "médicament", "traitement", "patient:"]
        for w in risky:
            self.assertNotIn(w.lower(), txt.lower(), f"RGPD: évite le mot '{w}' dans le SMS")

    @patch(OVH_REQUEST_PATCH_PATH, return_value={"ids": ["job_1"]})
    @patch(SEND_MAIL_PATCH_PATH, autospec=True)
    def test_none_no_notifications(self, mock_send_mail, mock_ovh_request):
        from core_emails.services_notifications import send_prescription_notifications

        self.ns.patient_channel = "NONE"
        self.ns.save()

        with self.captureOnCommitCallbacks(execute=True):

            
            send_prescription_notifications(prescription=self.rx)
        self._assert_no_email(mock_send_mail)
        self.assertEqual(mock_ovh_request.call_count, 0, "OVH ne doit pas être appelé")
        from core_notifications.models import SmsMessage
        self.assertEqual(SmsMessage.objects.count(), 0, "Aucun SMS ne doit être créé")

    @patch(OVH_REQUEST_PATCH_PATH, return_value={"ids": ["job_1"]})
    @patch(SEND_MAIL_PATCH_PATH, autospec=True)
    def test_patient_email_only(self, mock_send_mail, mock_ovh_request):
        from core_emails.services_notifications import send_prescription_notifications

        self.ns.patient_channel = "EMAIL"
        self.ns.save()

        with self.captureOnCommitCallbacks(execute=True):

            
            send_prescription_notifications(prescription=self.rx)
        self._assert_email_only_to_patient(mock_send_mail)
        self.assertEqual(mock_ovh_request.call_count, 0, "OVH ne doit pas être appelé")
        from core_notifications.models import SmsMessage
        self.assertEqual(SmsMessage.objects.count(), 0, "Aucun SMS ne doit être créé")

    @patch(OVH_REQUEST_PATCH_PATH, return_value={"ids": ["job_1"]})
    @patch(SEND_MAIL_PATCH_PATH, autospec=True)
    def test_patient_sms_only(self, mock_send_mail, mock_ovh_request):
        from core_emails.services_notifications import send_prescription_notifications

        self.ns.patient_channel = "SMS"
        self.ns.save()

        with self.captureOnCommitCallbacks(execute=True):

            
            send_prescription_notifications(prescription=self.rx)
        self._assert_no_email(mock_send_mail)
        self.assertGreaterEqual(mock_ovh_request.call_count, 1, "OVH doit être appelé pour envoyer un SMS")
        self._assert_sms_created_rgpd_safe()

    @patch(OVH_REQUEST_PATCH_PATH, return_value={"ids": ["job_1"]})
    @patch(SEND_MAIL_PATCH_PATH, autospec=True)
    def test_patient_both_sms_and_email(self, mock_send_mail, mock_ovh_request):
        from core_emails.services_notifications import send_prescription_notifications

        self.ns.patient_channel = "BOTH"
        self.ns.save()

        with self.captureOnCommitCallbacks(execute=True):

            
            send_prescription_notifications(prescription=self.rx)
        self._assert_email_only_to_patient(mock_send_mail)
        self.assertGreaterEqual(mock_ovh_request.call_count, 1, "OVH doit être appelé")
        self._assert_sms_created_rgpd_safe()
