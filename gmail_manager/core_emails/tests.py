import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core_patients.models import Patient

from .models import (
    Prescription,
    PrescriptionRenewalEvent,
    PrescriptionStatus,
    PrescriptionStatusHistory,
    PrescriptionType,
)
from .services import compute_renewals_watch_from_delivered


class RenewalTestMixin:
    today = datetime.date(2026, 9, 3)

    def create_renewal(self, *, days_left=5, renewal_times=2, done=0):
        patient = Patient.objects.create(
            full_name="Patient Test",
            email=f"patient-{Patient.objects.count()}@example.com",
            phone_number="+33600000000",
        )
        prescription = Prescription.objects.create(
            patient=patient,
            type=PrescriptionType.RENOUVELLEMENT,
            status=PrescriptionStatus.DELIVERED,
            established_at=self.today,
        )
        info = prescription.renewal_info
        info.renewal_times = renewal_times
        info.renewal_done_count = done
        info.period_days = 30
        info.save()

        due_date = self.today + datetime.timedelta(days=days_left)
        delivered_date = due_date - datetime.timedelta(days=(done + 1) * 30)
        history = PrescriptionStatusHistory.objects.create(
            prescription=prescription,
            old_status=PrescriptionStatus.READY,
            new_status=PrescriptionStatus.DELIVERED,
        )
        delivered_at = timezone.make_aware(
            datetime.datetime.combine(delivered_date, datetime.time(hour=12))
        )
        PrescriptionStatusHistory.objects.filter(pk=history.pk).update(
            changed_at=delivered_at
        )
        return prescription, info


class RenewalWatchTests(RenewalTestMixin, TestCase):
    def compute(self):
        now = timezone.make_aware(
            datetime.datetime.combine(self.today, datetime.time(hour=12))
        )
        with patch("core_emails.services.timezone.now", return_value=now):
            return compute_renewals_watch_from_delivered()

    def test_classifies_j5_j1_and_overdue(self):
        due_5, _ = self.create_renewal(days_left=5)
        due_1, _ = self.create_renewal(days_left=1)
        overdue, _ = self.create_renewal(days_left=-1)

        result_5, result_1, result_overdue = self.compute()

        self.assertEqual([p.pk for p in result_5], [due_5.pk])
        self.assertEqual([p.pk for p in result_1], [due_1.pk])
        self.assertEqual([p.pk for p in result_overdue], [overdue.pk])

    def test_ignores_completed_archived_and_never_delivered_renewals(self):
        completed, _ = self.create_renewal(days_left=5, renewal_times=1, done=1)
        archived, _ = self.create_renewal(days_left=5)
        archived.status = PrescriptionStatus.ARCHIVED
        archived.save(update_fields=["status"])
        never_delivered, _ = self.create_renewal(days_left=5)
        never_delivered.status_history.all().delete()

        result = self.compute()
        all_ids = {p.pk for group in result for p in group}

        self.assertNotIn(completed.pk, all_ids)
        self.assertNotIn(archived.pk, all_ids)
        self.assertNotIn(never_delivered.pk, all_ids)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RenewalActionTests(RenewalTestMixin, TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="pharmacist", password="test-password"
        )
        self.client.force_login(self.user)

    def test_dashboard_requires_authentication(self):
        self.client.logout()
        response = self.client.get(reverse("core_emails:renewals_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_email_cannot_be_sent_at_the_wrong_time(self):
        prescription, _ = self.create_renewal(days_left=5)

        with patch("core_emails.views.timezone.localdate", return_value=self.today):
            response = self.client.post(
                reverse("core_emails:send_renewal_patient_email", args=[prescription.pk, 1])
            )

        self.assertRedirects(response, reverse("core_emails:renewals_dashboard"))
        self.assertEqual(len(mail.outbox), 0)

    def test_completing_cycle_reuses_event_and_resets_reminders(self):
        prescription, info = self.create_renewal(days_left=5)
        sent_at = timezone.now()
        info.reminder_5_patient_email_sent_at = sent_at
        info.reminder_5_patient_sms_sent_at = sent_at
        info.reminder_1_patient_email_sent_at = sent_at
        info.reminder_1_patient_sms_sent_at = sent_at
        info.overdue_patient_email_sent_at = sent_at
        info.overdue_patient_sms_sent_at = sent_at
        info.save()
        PrescriptionRenewalEvent.objects.create(
            prescription=prescription,
            number=1,
            note="Rappel J-5",
        )

        response = self.client.post(
            reverse("core_emails:mark_renewal_done", args=[prescription.pk]),
            {"note": "Renouvellement réalisé"},
        )

        self.assertEqual(response.status_code, 302)
        info.refresh_from_db()
        self.assertEqual(info.renewal_done_count, 1)
        self.assertIsNone(info.reminder_5_patient_email_sent_at)
        self.assertIsNone(info.reminder_5_patient_sms_sent_at)
        self.assertIsNone(info.reminder_1_patient_email_sent_at)
        self.assertIsNone(info.reminder_1_patient_sms_sent_at)
        self.assertIsNone(info.overdue_patient_email_sent_at)
        self.assertIsNone(info.overdue_patient_sms_sent_at)
        self.assertEqual(
            PrescriptionRenewalEvent.objects.filter(
                prescription=prescription, number=1
            ).count(),
            1,
        )
