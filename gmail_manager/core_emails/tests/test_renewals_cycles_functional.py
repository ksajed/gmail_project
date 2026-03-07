
from __future__ import annotations

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from core_patients.models import Patient
from core_emails.models import (
    Prescription,
    PrescriptionType,
    PrescriptionStatus,
    PrescriptionRenewalInfo,
    PrescriptionRenewalCycle,
)


class RenewalCyclesFunctionalTests(TestCase):

    def setUp(self):

        U = get_user_model()
        self.user = U.objects.create_user(
            username="testuser",
            password="pass"
        )

        self.patient = Patient.objects.create(
            full_name="Patient Test",
            email="patient@example.com",
            phone_number="0612345678"
        )

        self.prescription = Prescription.objects.create(
            patient=self.patient,
            type=PrescriptionType.RENOUVELLEMENT,
            status=PrescriptionStatus.RECEIVED
        )

        info = self.prescription.renewal_info
        info.renewal_times = 2
        info.renewal_done_count = 0
        info.period_days = 30
        info.save()

    def test_cycle_creation(self):

        cycles = PrescriptionRenewalCycle.objects.filter(
            prescription=self.prescription
        )

        self.assertEqual(cycles.count(), 1)

        cycle = cycles.first()

        self.assertEqual(cycle.cycle_number, 1)
        self.assertEqual(cycle.status, PrescriptionStatus.RECEIVED)


    def test_cycle_progression(self):

        info = self.prescription.renewal_info

        # simulation renouvellement 1
        cycle1 = PrescriptionRenewalCycle.objects.get(
            prescription=self.prescription,
            cycle_number=1
        )

        cycle1.status = PrescriptionStatus.DELIVERED
        cycle1.closed_at = timezone.now()
        cycle1.save()

        info.renewal_done_count = 1
        info.save()

        cycle2 = PrescriptionRenewalCycle.objects.create(
            prescription=self.prescription,
            cycle_number=2,
            status=PrescriptionStatus.RECEIVED
        )

        self.assertEqual(cycle2.cycle_number, 2)

        # simulation renouvellement 2

        cycle2.status = PrescriptionStatus.DELIVERED
        cycle2.closed_at = timezone.now()
        cycle2.save()

        info.renewal_done_count = 2
        info.save()

        cycle3 = PrescriptionRenewalCycle.objects.create(
            prescription=self.prescription,
            cycle_number=3,
            status=PrescriptionStatus.RECEIVED
        )

        self.assertEqual(cycle3.cycle_number, 3)


    def test_max_renewals_limit(self):

        info = self.prescription.renewal_info
        info.renewal_done_count = 2
        info.save()

        allowed = info.renewal_done_count < info.renewal_times

        self.assertFalse(allowed)
