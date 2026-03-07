from __future__ import annotations

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test.client import RequestFactory

from core_patients.models import Patient
from core_emails.models import (
    Prescription,
    PrescriptionType,
    PrescriptionStatus,
    PrescriptionRenewalCycle,
)
from core_emails.views import mark_renewal_done


@override_settings(
    DEFAULT_FROM_EMAIL="no-reply@ordo.local",
    SERVER_EMAIL="server@ordo.local",
    ALLOWED_HOSTS=["localhost", "testserver"],
)
class RenewalCyclesArchivingFunctionalTests(TestCase):
    """
    renewal_times = 2  => 3 cycles total
    cycle 1 = initial
    cycle 2 = renouvellement 1
    cycle 3 = renouvellement 2
    archivage final seulement après cycle 3
    """

    def setUp(self):
        U = get_user_model()
        self.user = U.objects.create_user(username="u_arch", password="pass")

        self.patient = Patient.objects.create(
            full_name="Patient Archivage",
            email="patient.arch@example.com",
            phone_number="06 12 34 56 78",
        )

        self.rx = Prescription.objects.create(
            patient=self.patient,
            type=PrescriptionType.RENOUVELLEMENT,
            status=PrescriptionStatus.RECEIVED,
            created_by=self.user,
        )

        info = self.rx.renewal_info
        info.renewal_times = 2
        info.renewal_done_count = 0
        info.period_days = 30
        info.save()

        self.rf = RequestFactory()

    def _attach_messages(self, request):
        setattr(request, "session", {})
        storage = FallbackStorage(request)
        setattr(request, "_messages", storage)

    def _done(self, note):
        req = self.rf.post(f"/renewal/{self.rx.pk}/done/", data={"note": note})
        req.user = self.user
        self._attach_messages(req)
        return mark_renewal_done(req, pk=self.rx.pk)

    def test_full_workflow_with_archiving(self):
        # Cycle 1 auto
        c1 = PrescriptionRenewalCycle.objects.get(prescription=self.rx, cycle_number=1)
        self.assertEqual(c1.status, PrescriptionStatus.RECEIVED)
        self.assertIsNone(c1.closed_at)

        # DONE cycle 1 => crée cycle 2
        r1 = self._done("cycle 1")
        self.assertEqual(r1.status_code, 302)

        self.rx.refresh_from_db()
        self.assertEqual(self.rx.renewal_info.renewal_done_count, 1)

        c1.refresh_from_db()
        self.assertIsNotNone(c1.closed_at)

        c2 = PrescriptionRenewalCycle.objects.get(prescription=self.rx, cycle_number=2)
        self.assertEqual(c2.status, PrescriptionStatus.RECEIVED)
        self.assertIsNone(c2.closed_at)

        # l'ordonnance parent ne doit PAS être archivée après cycle 1
        self.rx.refresh_from_db()
        self.assertNotEqual(self.rx.status, PrescriptionStatus.ARCHIVED)

        # DONE cycle 2 => crée cycle 3
        r2 = self._done("cycle 2")
        self.assertEqual(r2.status_code, 302)

        self.rx.refresh_from_db()
        self.assertEqual(self.rx.renewal_info.renewal_done_count, 2)

        c2.refresh_from_db()
        self.assertIsNotNone(c2.closed_at)

        c3 = PrescriptionRenewalCycle.objects.get(prescription=self.rx, cycle_number=3)
        self.assertEqual(c3.status, PrescriptionStatus.RECEIVED)
        self.assertIsNone(c3.closed_at)

        # l'ordonnance parent ne doit PAS être archivée après cycle 2
        self.rx.refresh_from_db()
        self.assertNotEqual(self.rx.status, PrescriptionStatus.ARCHIVED)

        # DONE cycle 3 => refusé par la logique historique (renewal_times=2)
        r3 = self._done("cycle 3")
        self.assertEqual(r3.status_code, 302)

        self.rx.refresh_from_db()
        self.assertEqual(self.rx.renewal_info.renewal_done_count, 2)

        c3.refresh_from_db()
        self.assertIsNone(c3.closed_at)

        cycles = PrescriptionRenewalCycle.objects.filter(
            prescription=self.rx
        ).order_by("cycle_number")
        self.assertEqual(cycles.count(), 3)

        from core_emails.models import PrescriptionStatusHistory
        self.assertFalse(
            PrescriptionStatusHistory.objects.filter(
                prescription=self.rx,
                comment="Dernier cycle de renouvellement clôturé.",
            ).exists()
        )

        # Fin globale métier : le dernier cycle est clôturé,
        # sans imposer l'archivage automatique du dossier parent.
        self.assertNotEqual(self.rx.status, PrescriptionStatus.ARCHIVED)
