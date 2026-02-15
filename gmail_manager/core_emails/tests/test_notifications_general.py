from __future__ import annotations

from unittest.mock import patch
from django.test import TestCase, override_settings

from core_patients.models import Patient
from core_emails.models import (
    Prescription,
    PrescriptionStatus,
    PrescriptionType,
    PrescriptionNotificationSettings,
)

# send_mail est importé directement dans core_emails/services_notifications.py
SEND_MAIL_PATCH_PATH = "core_emails.services_notifications.send_mail"

# send_sms_logged utilise le backend OVH -> OvhSmsBackend._request
OVH_REQUEST_PATCH_PATH = "core_notifications.backends.ovh.OvhSmsBackend._request"


@override_settings(
    DEFAULT_FROM_EMAIL="no-reply@ordo.local",
    SERVER_EMAIL="server@ordo.local",
)
class NotificationsGeneralTests(TestCase):
    """
    Test général “réel” (changement de statut) :
    - Email : uniquement au patient (jamais à l'admin)
    - SMS : via send_sms_logged (backend OVH mocké), RGPD-safe
    - Respect channels NONE / SMS / EMAIL / BOTH
    """

    def setUp(self):
        self.admin_email = "khalidsajed19755@gmail.com"  # ne doit JAMAIS recevoir

        self.patient = Patient.objects.create(
            full_name="Patient Test",
            email="patient@example.com",
            phone_number="06 12 34 56 78",
        )

        self.rx = Prescription.objects.create(
            patient=self.patient,
            status=PrescriptionStatus.RECEIVED,
            type=PrescriptionType.INCOMPLETE,
        )

        self.ns = PrescriptionNotificationSettings.objects.create(
            prescription=self.rx,
            patient_channel="NONE",
            nurse_channel="NONE",
            free_text_message="Votre statut a changé.",
        )

    def _assert_email_only_to_patient(self, mock_send_mail):
        self.assertTrue(
            mock_send_mail.called,
            "send_mail doit être appelé quand channel EMAIL/BOTH",
        )
        _, kwargs = mock_send_mail.call_args
        recipient_list = kwargs.get("recipient_list") or []

        self.assertEqual(
            recipient_list,
            [self.patient.email],
            "Email doit être envoyé uniquement au patient",
        )

        forbidden = {
            self.admin_email,
            "no-reply@ordo.local",
            "server@ordo.local",
            "smtp-user@ordo.local",
        }
        self.assertTrue(
            forbidden.isdisjoint(set(recipient_list)),
            f"Interdit: email vers {forbidden & set(recipient_list)}",
        )

    def _assert_no_email(self, mock_send_mail):
        self.assertFalse(mock_send_mail.called, "Aucun email ne doit partir")

    def _assert_sms_created_rgpd_safe(self):
        from core_notifications.models import SmsMessage

        self.assertEqual(SmsMessage.objects.count(), 1, "Un SmsMessage doit être créé")
        sms = SmsMessage.objects.latest("id")

        # téléphone normalisé
        self.assertTrue(
            (sms.recipient_phone or "").startswith("+33"),
            "Le téléphone doit être normalisé en E.164 (+33...)",
        )

        txt = (getattr(sms, "rendered_text", None) or getattr(sms, "text", None) or "")
        self.assertNotIn("@", txt, "RGPD: pas d'email dans le SMS")

        # vérif “light” (à garder simple)
        risky = ["ordonnance", "médicament", "traitement", "patient:"]
        for w in risky:
            self.assertNotIn(w.lower(), txt.lower(), f"RGPD: évite le mot '{w}' dans le SMS")

    def _trigger_real_status_change(self):
        """
        IMPORTANT : on passe par le vrai workflow.
        Appel robuste : s'adapte à la signature réelle de change_prescription_status().
        """
        from core_emails.services import change_prescription_status
        import inspect

        sig = inspect.signature(change_prescription_status)
        params = sig.parameters

        # kwargs que l'on aimerait passer (best-effort)
        candidate_kwargs = {
            "prescription": self.rx,
            "new_status": PrescriptionStatus.IN_PROGRESS,
            "comment": "test",
            "changed_by": None,
            "user": None,
            "actor": None,
            "by": None,
            "performed_by": None,
        }

        # on ne garde que ceux acceptés
        kwargs = {k: v for k, v in candidate_kwargs.items() if k in params}

        # fallback : si la fonction est plutôt positionnelle (rare), on tente proprement
        if "prescription" not in kwargs and len(params) >= 1:
            # 1er param
            first = next(iter(params))
            kwargs[first] = self.rx

        if "new_status" not in kwargs:
            # trouve un param qui ressemble à "status"
            for name in params:
                if "status" in name and name not in kwargs:
                    kwargs[name] = PrescriptionStatus.IN_PROGRESS
                    break

        # exécute
        return change_prescription_status(**kwargs)


    @patch(OVH_REQUEST_PATCH_PATH, return_value={"ids": ["job_1"]})
    @patch(SEND_MAIL_PATCH_PATH, autospec=True)
    def test_none_no_notifications(self, mock_send_mail, mock_ovh_request):
        self.ns.patient_channel = "NONE"
        self.ns.save()

        with self.captureOnCommitCallbacks(execute=True):
            self._trigger_real_status_change()

        self._assert_no_email(mock_send_mail)
        self.assertEqual(mock_ovh_request.call_count, 0, "OVH ne doit pas être appelé")

        from core_notifications.models import SmsMessage
        self.assertEqual(SmsMessage.objects.count(), 0, "Aucun SMS ne doit être créé")

    @patch(OVH_REQUEST_PATCH_PATH, return_value={"ids": ["job_1"]})
    @patch(SEND_MAIL_PATCH_PATH, autospec=True)
    def test_patient_email_only(self, mock_send_mail, mock_ovh_request):
        self.ns.patient_channel = "EMAIL"
        self.ns.save()

        with self.captureOnCommitCallbacks(execute=True):
            self._trigger_real_status_change()

        self._assert_email_only_to_patient(mock_send_mail)
        self.assertEqual(mock_ovh_request.call_count, 0, "OVH ne doit pas être appelé")

        from core_notifications.models import SmsMessage
        self.assertEqual(SmsMessage.objects.count(), 0, "Aucun SMS ne doit être créé")

    @patch(OVH_REQUEST_PATCH_PATH, return_value={"ids": ["job_1"]})
    @patch(SEND_MAIL_PATCH_PATH, autospec=True)
    def test_patient_sms_only(self, mock_send_mail, mock_ovh_request):
        self.ns.patient_channel = "SMS"
        self.ns.save()

        with self.captureOnCommitCallbacks(execute=True):
            self._trigger_real_status_change()

        self._assert_no_email(mock_send_mail)
        self.assertGreaterEqual(
            mock_ovh_request.call_count, 1, "OVH doit être appelé pour envoyer un SMS"
        )
        self._assert_sms_created_rgpd_safe()

    @patch(OVH_REQUEST_PATCH_PATH, return_value={"ids": ["job_1"]})
    @patch(SEND_MAIL_PATCH_PATH, autospec=True)
    def test_patient_both_sms_and_email(self, mock_send_mail, mock_ovh_request):
        self.ns.patient_channel = "BOTH"
        self.ns.save()

        with self.captureOnCommitCallbacks(execute=True):
            self._trigger_real_status_change()

        self._assert_email_only_to_patient(mock_send_mail)
        self.assertGreaterEqual(mock_ovh_request.call_count, 1, "OVH doit être appelé")
        self._assert_sms_created_rgpd_safe()
