from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core_patients.models import Patient
from core_emails.models import (
    Prescription,
    PrescriptionType,
    PrescriptionStatus,
    PrescriptionRenewalInfo,
    PrescriptionRenewalCycle,
    PrescriptionStatusHistory,
)
from core_emails.services_renewal_rules import get_final_renewals


def _change_status(prescription, new_status, user=None):
    """
    Appelle le service réel de changement de statut.

    Compatible avec les signatures existantes dans Ordo :
    - core_emails.services_workflow.change_prescription_status
    - core_emails.services.change_prescription_status

    Le test doit utiliser le workflow réel, pas créer les cycles à la main.
    """
    candidates = []

    try:
        from core_emails.services_workflow import change_prescription_status
        candidates.append(change_prescription_status)
    except Exception:
        pass

    try:
        from core_emails.services import change_prescription_status
        candidates.append(change_prescription_status)
    except Exception:
        pass

    last_error = None

    for func in candidates:
        attempts = [
            lambda: func(
                prescription=prescription,
                new_status=new_status,
                changed_by=user,
                comment="Test régression renouvellement V9",
            ),
            lambda: func(
                prescription=prescription,
                new_status=new_status,
                user=user,
                comment="Test régression renouvellement V9",
            ),
            lambda: func(
                prescription,
                new_status,
                user,
                "Test régression renouvellement V9",
            ),
            lambda: func(
                prescription,
                new_status,
                user,
            ),
            lambda: func(
                prescription,
                new_status,
            ),
        ]

        for attempt in attempts:
            try:
                return attempt()
            except TypeError as e:
                last_error = e
                continue

    raise AssertionError(
        "Impossible d'appeler change_prescription_status avec les signatures connues. "
        f"Dernière erreur : {last_error}"
    )


class RenewalsV9RegressionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="tester-renewals-v9",
            password="testpass123",
        )

        self.patient = Patient.objects.create(
            email="regression.patient@example.com",
            phone_number="+33600000001",
        )

        self.prescription = Prescription.objects.create(
            patient=self.patient,
            type=PrescriptionType.RENOUVELLEMENT,
            status=PrescriptionStatus.RECEIVED,
            established_at=date(2026, 6, 1),
        )

        self.info, _ = PrescriptionRenewalInfo.objects.get_or_create(
            prescription=self.prescription,
        )
        self.info.renewal_times = 2
        self.info.renewal_done_count = 0
        self.info.period_days = 30
        self.info.save()

        PrescriptionRenewalCycle.objects.get_or_create(
            prescription=self.prescription,
            cycle_number=1,
            defaults={"status": PrescriptionStatus.RECEIVED},
        )

    def _reload(self):
        self.prescription.refresh_from_db()
        self.info.refresh_from_db()

    def _deliver_current_cycle(self):
        """
        Simule le workflow complet :
        RECEIVED -> IN_PROGRESS -> READY -> DELIVERED
        """
        _change_status(self.prescription, PrescriptionStatus.IN_PROGRESS, self.user)
        self.prescription.refresh_from_db()

        _change_status(self.prescription, PrescriptionStatus.READY, self.user)
        self.prescription.refresh_from_db()

        _change_status(self.prescription, PrescriptionStatus.DELIVERED, self.user)
        self.prescription.refresh_from_db()
        self.info.refresh_from_db()

    def test_cycle_1_delivered_creates_cycle_2_without_extra_cycle(self):
        self._deliver_current_cycle()

        cycles = PrescriptionRenewalCycle.objects.filter(
            prescription=self.prescription
        ).order_by("cycle_number")

        self.assertEqual(cycles.count(), 2)

        c1 = cycles.get(cycle_number=1)
        c2 = cycles.get(cycle_number=2)

        self.assertEqual(c1.status, PrescriptionStatus.DELIVERED)
        self.assertIsNotNone(c1.closed_at)

        self.assertEqual(c2.status, PrescriptionStatus.RECEIVED)
        self.assertIsNone(c2.closed_at)

        self.assertFalse(
            PrescriptionRenewalCycle.objects.filter(
                prescription=self.prescription,
                cycle_number=3,
            ).exists()
        )

    def test_never_more_than_one_open_cycle_after_delivery(self):
        self._deliver_current_cycle()

        open_cycles = PrescriptionRenewalCycle.objects.filter(
            prescription=self.prescription,
            closed_at__isnull=True,
        )

        self.assertEqual(open_cycles.count(), 1)
        self.assertEqual(open_cycles.first().cycle_number, 2)

    def test_renewal_done_count_never_decreases(self):
        before = int(self.info.renewal_done_count)

        self._deliver_current_cycle()
        self._reload()

        after_first_delivery = int(self.info.renewal_done_count)

        self.assertGreaterEqual(after_first_delivery, before)

        self._deliver_current_cycle()
        self._reload()

        after_second_delivery = int(self.info.renewal_done_count)

        self.assertGreaterEqual(after_second_delivery, after_first_delivery)

    def test_no_cycle_created_after_final_cycle_delivered(self):
        """
        renewal_times = 2 signifie total patient = 3 cycles.
        Après livraison du cycle 3, aucun cycle 4 ne doit exister.
        """
        self._deliver_current_cycle()
        self._deliver_current_cycle()
        self._deliver_current_cycle()

        self.assertFalse(
            PrescriptionRenewalCycle.objects.filter(
                prescription=self.prescription,
                cycle_number=4,
            ).exists()
        )

    def test_final_cycle_detected_by_business_rule(self):
        """
        Le cycle 3/3 doit être détecté comme dernier renouvellement.
        """
        # Amener l'ordonnance au cycle 3 ouvert.
        self._deliver_current_cycle()
        self._deliver_current_cycle()

        cycle3 = PrescriptionRenewalCycle.objects.get(
            prescription=self.prescription,
            cycle_number=3,
        )

        self.assertIsNone(cycle3.closed_at)
        self.assertEqual(cycle3.status, PrescriptionStatus.RECEIVED)

        items = get_final_renewals(today=date(2026, 6, 8))

        matched = [
            item for item in items
            if item.get("prescription") == self.prescription
        ]

        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["current_cycle_number"], 3)
        self.assertEqual(matched[0]["total_cycles"], 3)
        self.assertEqual(matched[0]["remaining_until_final"], 0)

    def test_notification_markers_are_not_copied_to_next_cycle(self):
        """
        Si le cycle 1 avait des rappels marqués,
        le cycle 2 ouvert doit repartir propre.
        """
        cycle1 = PrescriptionRenewalCycle.objects.get(
            prescription=self.prescription,
            cycle_number=1,
        )

        now = timezone.now()
        cycle1.reminder_5_patient_sms_sent_at = now
        cycle1.reminder_5_patient_email_sent_at = now
        cycle1.reminder_3_patient_sms_sent_at = now
        cycle1.reminder_3_patient_email_sent_at = now
        cycle1.save()

        self._deliver_current_cycle()

        cycle2 = PrescriptionRenewalCycle.objects.get(
            prescription=self.prescription,
            cycle_number=2,
        )

        self.assertIsNone(cycle2.reminder_5_patient_sms_sent_at)
        self.assertIsNone(cycle2.reminder_5_patient_email_sent_at)
        self.assertIsNone(cycle2.reminder_3_patient_sms_sent_at)
        self.assertIsNone(cycle2.reminder_3_patient_email_sent_at)

    def test_status_history_is_preserved_after_cycle_transitions(self):
        self._deliver_current_cycle()

        history_count = PrescriptionStatusHistory.objects.filter(
            prescription=self.prescription,
        ).count()

        self.assertGreaterEqual(history_count, 3)

        delivered_exists = PrescriptionStatusHistory.objects.filter(
            prescription=self.prescription,
            new_status=PrescriptionStatus.DELIVERED,
        ).exists()

        self.assertTrue(delivered_exists)
