from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from core_notifications.models import SmsMessage, SmsStatus
from core_notifications.services import send_sms_logged
from core_notifications.models import SmsPurpose


class SendSmsLoggedHardeningTests(TestCase):
    @patch("core_notifications.services.OvhSmsBackend.send", autospec=True)
    def test_normalizes_fr_number_to_e164(self, mock_send):
        mock_send.return_value = {"ids": ["job_123"]}

        sms = send_sms_logged(
            to_e164="0601020304",
            text="Bonjour. Statut ordonnance : Reçue. Merci.",
            purpose=SmsPurpose.INFO,
            template_key="status_update",
            prescription=None,
        )

        self.assertEqual(sms.recipient_phone, "+33601020304")
        self.assertEqual(sms.status, SmsStatus.SENT)
        # vérifie que l'appel OVH reçoit le numéro normalisé
        args, kwargs = mock_send.call_args
        # signature (self, to, text) car autospec=True
        self.assertEqual(args[1], "+33601020304")
        self.assertIn("Statut", args[2])

    @patch("core_notifications.services.OvhSmsBackend.send", autospec=True)
    def test_rgpd_blocks_email_address(self, mock_send):
        mock_send.return_value = {"ids": ["job_123"]}

        with self.assertRaises(ValueError):
            send_sms_logged(
                to_e164="+33601020304",
                text="Contact: patient@example.com",
                purpose=SmsPurpose.INFO,
                template_key="status_update",
                prescription=None,
            )

        mock_send.assert_not_called()
        self.assertEqual(SmsMessage.objects.count(), 0)

    @patch("core_notifications.services.OvhSmsBackend.send", autospec=True)
    def test_rgpd_blocks_medical_markers(self, mock_send):
        mock_send.return_value = {"ids": ["job_123"]}

        with self.assertRaises(ValueError):
            send_sms_logged(
                to_e164="+33601020304",
                text="Prendre 500 mg matin et soir",
                purpose=SmsPurpose.INFO,
                template_key="free_text",
                prescription=None,
            )

        mock_send.assert_not_called()
        self.assertEqual(SmsMessage.objects.count(), 0)

    @patch("core_notifications.services.OvhSmsBackend.send", autospec=True)
    def test_soft_dedupe_returns_existing_message(self, mock_send):
        mock_send.return_value = {"ids": ["job_123"]}

        sms1 = send_sms_logged(
            to_e164="+33601020304",
            text="Bonjour. Statut ordonnance : En cours. Merci.",
            purpose=SmsPurpose.INFO,
            template_key="status_update",
            prescription=None,
        )
        sms2 = send_sms_logged(
            to_e164="+33601020304",
            text="Bonjour. Statut ordonnance : En cours. Merci.",
            purpose=SmsPurpose.INFO,
            template_key="status_update",
            prescription=None,
        )

        self.assertEqual(sms1.id, sms2.id)
        self.assertEqual(SmsMessage.objects.count(), 1)
        # OVH ne doit être appelé qu'une fois
        self.assertEqual(mock_send.call_count, 1)
