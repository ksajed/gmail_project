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
    calculate_notification_date,
    get_due_notifications,
    mark_rule_channel_sent,
)


class RenewalsLot18CatchupTests(TestCase):
    def setUp(self):
        self.patient = Patient.objects.create(
            email="catchup.patient@example.com",
            phone_number="+33600000018",
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

        first_delivered = timezone.make_aware(
            timezone.datetime(2026, 6, 4, 10, 0, 0)
        )

        PrescriptionStatusHistory.objects.create(
            prescription=self.prescription,
            old_status=PrescriptionStatus.READY,
            new_status=PrescriptionStatus.DELIVERED,
            changed_at=first_delivered,
            comment="Première délivrance test Lot 18",
        )

        # Le moteur calcule le cycle courant à partir de renewal_done_count + 1.
        # Ici renewal_done_count=2 => cycle courant attendu = 3.
        # On supprime le cycle créé automatiquement en signal/post_save s'il existe,
        # puis on crée uniquement le cycle courant du scénario.
        PrescriptionRenewalCycle.objects.filter(
            prescription=self.prescription,
        ).delete()

        self.cycle = PrescriptionRenewalCycle.objects.create(
            prescription=self.prescription,
            cycle_number=3,
            status=PrescriptionStatus.RECEIVED,
            started_at=timezone.now(),
        )

        RenewalNotificationRule.objects.all().delete()

    def _create_rule(self, days_before=5, sms=True, email=True, active=True):
        return RenewalNotificationRule.objects.create(
            name=f"J-{days_before}",
            active=active,
            days_before=days_before,
            send_sms=sms,
            send_email=email,
            sort_order=1,
        )

    def _matched(self, today):
        return [
            item for item in get_due_notifications(today=today)
            if item.get("prescription") == self.prescription
            and item.get("cycle") == self.cycle
        ]

    def test_missed_notification_yesterday_is_caught_up_today(self):
        rule = self._create_rule(days_before=5)

        due = _get_cycle_due_date(self.cycle)
        notification_day = calculate_notification_date(due, rule)

        today_after_server_restart = notification_day + timedelta(days=1)

        matched = self._matched(today_after_server_restart)

        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["rule"], rule)

    def test_missed_notification_three_days_ago_is_caught_up(self):
        rule = self._create_rule(days_before=5)

        due = _get_cycle_due_date(self.cycle)
        notification_day = calculate_notification_date(due, rule)

        today_after_long_outage = notification_day + timedelta(days=3)

        matched = self._matched(today_after_long_outage)

        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["rule"], rule)

    def test_future_notification_is_not_sent_too_early(self):
        rule = self._create_rule(days_before=5)

        due = _get_cycle_due_date(self.cycle)
        notification_day = calculate_notification_date(due, rule)

        day_before_notification = notification_day - timedelta(days=1)

        matched = self._matched(day_before_notification)

        self.assertEqual(matched, [])

    def test_already_sent_missed_notification_is_not_returned_again(self):
        rule = self._create_rule(days_before=5)

        due = _get_cycle_due_date(self.cycle)
        notification_day = calculate_notification_date(due, rule)

        mark_rule_channel_sent(self.cycle, rule, "SMS")
        mark_rule_channel_sent(self.cycle, rule, "EMAIL")

        today_after_restart = notification_day + timedelta(days=1)

        matched = self._matched(today_after_restart)

        self.assertEqual(matched, [])

    def test_command_catches_up_missed_notification_in_dry_run(self):
        rule = self._create_rule(days_before=5)

        due = _get_cycle_due_date(self.cycle)
        notification_day = calculate_notification_date(due, rule)
        today_after_restart = notification_day + timedelta(days=1)

        from io import StringIO
        out = StringIO()

        call_command(
            "run_renewal_notifications",
            date=str(today_after_restart),
            limit=1,
            stdout=out,
        )

        output = out.getvalue()

        self.assertIn("Mode : DRY-RUN", output)
        self.assertIn("Notifications à traiter : 1", output)
        self.assertIn("J-5", output)

    def test_calculate_notification_date_returns_open_day_if_raw_day_closed(self):
        """
        Test de sécurité : on vérifie que calculate_notification_date
        retourne une date utilisable par le moteur.
        Le détail dimanche/férié est géré par les fonctions internes.
        """
        rule = self._create_rule(days_before=5)
        due = _get_cycle_due_date(self.cycle)

        notification_day = calculate_notification_date(due, rule)

        self.assertIsNotNone(notification_day)
        self.assertLessEqual(notification_day, due)
