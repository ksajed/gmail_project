from datetime import date, timedelta

from django.core.management import call_command
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
    RenewalNotificationRule,
)
from core_emails.services_renewal_rules import (
    _get_cycle_due_date,
    get_due_notifications,
    get_final_renewals,
    get_activity_metrics,
    mark_rule_channel_sent,
)


class RenewalsV9EngineTests(TestCase):
    def setUp(self):
        self.patient = Patient.objects.create(
            email="patient.v9@example.com",
            phone_number="+33600000000",
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
        self.info.renewal_done_count = 2
        self.info.period_days = 30
        self.info.save()

        self.first_delivered = timezone.make_aware(
            timezone.datetime(2026, 6, 4, 10, 0, 0)
        )

        delivered_history = PrescriptionStatusHistory.objects.create(
            prescription=self.prescription,
            old_status=PrescriptionStatus.READY,
            new_status=PrescriptionStatus.DELIVERED,
            comment="Première délivrance test V9",
        )
        PrescriptionStatusHistory.objects.filter(pk=delivered_history.pk).update(
            changed_at=self.first_delivered,
        )

        # Le signal initialise le cycle 1. Ce scénario teste explicitement le
        # cycle 3, donc aucun ancien cycle ne doit rester actif.
        self.prescription.renewal_cycles.all().delete()
        self.cycle = PrescriptionRenewalCycle.objects.create(
            prescription=self.prescription,
            cycle_number=3,
            status=PrescriptionStatus.RECEIVED,
            started_at=timezone.now(),
        )

        RenewalNotificationRule.objects.all().delete()
        self.rule = RenewalNotificationRule.objects.create(
            name="TEST J-5",
            active=True,
            days_before=5,
            send_sms=True,
            send_email=True,
            sort_order=1,
        )

    def test_due_date_uses_first_delivered_plus_cycle_period(self):
        due = _get_cycle_due_date(self.cycle)
        self.assertEqual(due, date(2026, 9, 2))

    def test_due_notifications_detects_j5(self):
        due = _get_cycle_due_date(self.cycle)
        notification_day = due - timedelta(days=5)

        items = get_due_notifications(today=notification_day)

        self.assertTrue(
            any(
                item.get("prescription") == self.prescription
                and item.get("cycle") == self.cycle
                for item in items
            )
        )

    def test_final_renewal_detected_on_last_cycle(self):
        items = get_final_renewals(today=date(2026, 6, 7))

        matched = [
            item for item in items
            if item.get("prescription") == self.prescription
        ]

        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["current_cycle_number"], 3)
        self.assertEqual(matched[0]["total_cycles"], 3)
        self.assertEqual(matched[0]["remaining_until_final"], 0)

    def test_activity_metrics_returns_safe_integer_values(self):
        metrics = get_activity_metrics(today=date(2026, 6, 7))

        expected_keys = [
            "sms_sent_today",
            "emails_sent_today",
            "cycles_created_today",
            "cycles_closed_today",
            "overdue_detected",
            "urgent_detected",
        ]

        for key in expected_keys:
            self.assertIn(key, metrics)
            self.assertIsInstance(metrics[key], int)

    def test_activity_metrics_counts_dynamic_email_deliveries_and_doctor_email(self):
        second_rule = RenewalNotificationRule.objects.create(
            name="TEST J-5 EMAIL B",
            active=True,
            days_before=5,
            send_sms=False,
            send_email=True,
            sort_order=2,
        )
        sent_at = timezone.make_aware(
            timezone.datetime(2026, 6, 7, 12, 0, 0)
        )
        mark_rule_channel_sent(
            self.cycle,
            self.rule,
            "EMAIL",
            sent_at=sent_at,
        )
        mark_rule_channel_sent(
            self.cycle,
            second_rule,
            "EMAIL",
            sent_at=sent_at,
        )
        self.cycle.doctor_email_sent_at = sent_at
        self.cycle.save(update_fields=["doctor_email_sent_at"])

        metrics = get_activity_metrics(today=date(2026, 6, 7))

        self.assertEqual(metrics["emails_sent_today"], 3)

    def test_command_dry_run_does_not_mark_cycle_as_sent(self):
        due = _get_cycle_due_date(self.cycle)
        notification_day = due - timedelta(days=5)

        call_command(
            "run_renewal_notifications",
            date=str(notification_day),
            limit=1,
        )

        self.cycle.refresh_from_db()

        self.assertIsNone(self.cycle.reminder_5_patient_sms_sent_at)
        self.assertIsNone(self.cycle.reminder_5_patient_email_sent_at)

    def test_already_sent_j5_is_not_returned_again(self):
        mark_rule_channel_sent(self.cycle, self.rule, "SMS")
        mark_rule_channel_sent(self.cycle, self.rule, "EMAIL")

        due = _get_cycle_due_date(self.cycle)
        notification_day = due - timedelta(days=5)

        items = get_due_notifications(today=notification_day)

        self.assertFalse(
            any(item.get("prescription") == self.prescription for item in items)
        )
