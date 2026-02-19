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

SEND_MAIL_PATCH_PATH = "core_emails.services_notifications.send_mail"
OVH_REQUEST_PATCH_PATH = "core_notifications.backends.ovh.OvhSmsBackend._request"


@override_settings(
    DEFAULT_FROM_EMAIL="no-reply@ordo.local",
    SERVER_EMAIL="server@ordo.local",
)
class NotificationsMatrixTests(TestCase):
    def setUp(self):
        self.admin_email = "khalidsajed19755@gmail.com"

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
            free_text_message="Message libre (test).",
        )

    # ----------------------------
    # Helpers: introspection
    # ----------------------------
    def _fieldset(self, model) -> set[str]:
        return {f.name for f in model._meta.get_fields() if getattr(f, "concrete", False)}

    def _create_nurse_obj(self):
        """
        Crée un objet infirmier (core_people.Person) en détectant les champs existants.
        (Ton Person n'a pas 'full_name' chez toi.)
        """
        from core_people.models import Person

        fields = self._fieldset(Person)

        kwargs = {}

        # Identité / nom
        if "full_name" in fields:
            kwargs["full_name"] = "Inf Test"
        elif "name" in fields:
            kwargs["name"] = "Inf Test"
        elif "first_name" in fields and "last_name" in fields:
            kwargs["first_name"] = "Inf"
            kwargs["last_name"] = "Test"

        # Email
        if "email" in fields:
            kwargs["email"] = "nurse@example.com"

        # Téléphone
        if "phone_number" in fields:
            kwargs["phone_number"] = "06 99 88 77 66"
        elif "phone" in fields:
            kwargs["phone"] = "06 99 88 77 66"
        elif "mobile" in fields:
            kwargs["mobile"] = "06 99 88 77 66"

        # Certains modèles exigent un champ "role"/"kind"/etc — on ne guess pas.
        # Si ton Person a des champs requis non gérés ici, le test te le dira clairement.
        return Person.objects.create(**kwargs)

    def _attach_nurse_if_possible(self, nurse):
        """
        Associe l’infirmière à la prescription :
        - rx.assigned_nurse si existe
        - sinon PrescriptionAssignment (best-effort sur le nom de champ : nurse/person)
        """
        rx_fields = self._fieldset(self.rx.__class__)
        if "assigned_nurse" in rx_fields:
            self.rx.assigned_nurse = nurse
            self.rx.save(update_fields=["assigned_nurse"])
            return

        # Fallback: PrescriptionAssignment (si présent)
        try:
            from core_emails.models_assignment import PrescriptionAssignment
        except Exception as e:
            raise RuntimeError(
                "Impossible d'associer une infirmière : ni champ Prescription.assigned_nurse "
                "ni core_emails.models_assignment.PrescriptionAssignment importable."
            ) from e

        pa_fields = self._fieldset(PrescriptionAssignment)

        kwargs = {"prescription": self.rx}
        if "nurse" in pa_fields:
            kwargs["nurse"] = nurse
        elif "person" in pa_fields:
            kwargs["person"] = nurse
        else:
            raise RuntimeError(
                f"PrescriptionAssignment trouvé mais aucun champ 'nurse'/'person'. Champs={sorted(pa_fields)}"
            )

        PrescriptionAssignment.objects.create(**kwargs)

    # ----------------------------
    # Helpers: expected
    # ----------------------------
    def _expected_actions(self, channel: str) -> tuple[int, int]:
        """
        Retourne (emails_count, sms_count)
        """
        c = (channel or "NONE").upper()
        if c == "NONE":
            return (0, 0)
        if c == "EMAIL":
            return (1, 0)
        if c == "SMS":
            return (0, 1)
        if c == "BOTH":
            return (1, 1)
        raise ValueError(f"Canal inconnu: {channel}")

    def _assert_emails(
        self,
        mock_send_mail,
        expected_patient_emails: int,
        expected_nurse_emails: int,
        nurse_email: str | None,
    ):
        calls = list(mock_send_mail.call_args_list)

        recipients_lists: list[list[str]] = []
        for _args, kwargs in calls:
            rl = kwargs.get("recipient_list") or []
            recipients_lists.append(list(rl))

        forbidden = {
            self.admin_email,
            "no-reply@ordo.local",
            "server@ordo.local",
            "smtp-user@ordo.local",
        }
        for rl in recipients_lists:
            self.assertTrue(
                forbidden.isdisjoint(set(rl)),
                f"Interdit: email vers {forbidden & set(rl)}",
            )

        patient_hits = sum(1 for rl in recipients_lists if rl == [self.patient.email])
        nurse_hits = 0
        if nurse_email:
            nurse_hits = sum(1 for rl in recipients_lists if rl == [nurse_email])

        self.assertEqual(patient_hits, expected_patient_emails)
        self.assertEqual(nurse_hits, expected_nurse_emails)

        self.assertEqual(
            len(recipients_lists),
            expected_patient_emails + expected_nurse_emails,
            f"Nombre total d'emails inattendu: {recipients_lists}",
        )

    def _assert_sms(self, expected_sms_count: int):
        from core_notifications.models import SmsMessage

        self.assertEqual(SmsMessage.objects.count(), expected_sms_count)

        for sms in SmsMessage.objects.all().order_by("id"):
            self.assertTrue((sms.recipient_phone or "").startswith("+33"))
            txt = (sms.rendered_text or "")
            self.assertNotIn("@", txt)

    def _trigger_real_status_change(self):
        """
        IMPORTANT: on remet RECEIVED avant chaque sous-test,
        sinon Ordo refuse 'statut identique'.
        """
        from core_emails.services import change_prescription_status

        # reset DB direct
        Prescription.objects.filter(pk=self.rx.pk).update(status=PrescriptionStatus.RECEIVED)
        self.rx.refresh_from_db()

        change_prescription_status(
            prescription=self.rx,
            new_status=PrescriptionStatus.IN_PROGRESS,
            user=None,
            comment="test matrix",
        )

    # ----------------------------
    # TEST MATRIX
    # ----------------------------
    @patch(OVH_REQUEST_PATCH_PATH, return_value={"ids": ["job_1"]})
    @patch(SEND_MAIL_PATCH_PATH, autospec=True)
    def test_all_channels_matrix(self, mock_send_mail, mock_ovh_request):
        from core_notifications.models import SmsMessage

        channels = ["NONE", "EMAIL", "SMS", "BOTH"]
        nurse_modes = [False, True]

        for has_nurse in nurse_modes:
            nurse = None
            nurse_email = None

            if has_nurse:
                nurse = self._create_nurse_obj()
                nurse_email = getattr(nurse, "email", None)
                self._attach_nurse_if_possible(nurse)

            for pc in channels:
                for nc in channels:
                    mock_send_mail.reset_mock()
                    mock_ovh_request.reset_mock()
                    SmsMessage.objects.all().delete()

                    self.ns.patient_channel = pc
                    self.ns.nurse_channel = nc
                    self.ns.save(update_fields=["patient_channel", "nurse_channel"])

                    with self.subTest(has_nurse=has_nurse, patient_channel=pc, nurse_channel=nc):
                        self._trigger_real_status_change()

                        pe, ps = self._expected_actions(pc)
                        if has_nurse:
                            ne, ns = self._expected_actions(nc)
                        else:
                            ne, ns = (0, 0)

                        self._assert_emails(mock_send_mail, pe, ne, nurse_email)

                        expected_sms = ps + ns
                        self._assert_sms(expected_sms)

                        self.assertEqual(
                            mock_ovh_request.call_count,
                            expected_sms,
                            f"OVH _request attendu={expected_sms}",
                        )
