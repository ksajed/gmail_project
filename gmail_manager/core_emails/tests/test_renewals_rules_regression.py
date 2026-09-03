from datetime import date, timedelta
from io import StringIO

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
    calculate_notification_date,
)


class RenewalDefaultPolicyTests(TestCase):
    def test_only_j5_and_j1_are_active_by_default(self):
        active_days = set(
            RenewalNotificationRule.objects.filter(active=True)
            .values_list("days_before", flat=True)
        )

        self.assertEqual(active_days, {5, 1})


class RenewalsRulesRegressionTests(TestCase):
    """
    Tests de régression des règles configurables V9.

    Philosophie métier :
    Le moteur ne connaît pas J-5 / J-10 / J-21 en dur.
    Il lit uniquement les règles configurées par le pharmacien.
    """

    def setUp(self):
        self.patient = Patient.objects.create(
            email="rules.patient@example.com",
            phone_number="+33600000002",
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
            comment="Première délivrance test règles dynamiques",
        )

        # Le signal de création initialise le cycle 1. Ce scénario place
        # volontairement l'ordonnance au cycle 3 : l'ancien cycle ne doit pas
        # rester actif, sinon chaque règle produit deux notifications.
        self.prescription.renewal_cycles.all().delete()
        self.cycle = PrescriptionRenewalCycle.objects.create(
            prescription=self.prescription,
            cycle_number=3,
            status=PrescriptionStatus.RECEIVED,
            started_at=timezone.now(),
        )

        RenewalNotificationRule.objects.all().delete()

    def _due_date(self):
        due = _get_cycle_due_date(self.cycle)
        self.assertIsNotNone(due)
        return due

    def _day_for_rule(self, days_before):
        """
        Date réelle de notification selon le moteur V9.

        Important :
        la date brute due_date - days_before peut être déplacée
        si elle tombe sur un jour fermé.
        """
        temp_rule = RenewalNotificationRule(days_before=days_before)
        return calculate_notification_date(self._due_date(), temp_rule)

    def _create_rule(
        self,
        *,
        name="TEST",
        active=True,
        days_before=5,
        send_sms=True,
        send_email=True,
        sort_order=1,
    ):
        return RenewalNotificationRule.objects.create(
            name=name,
            active=active,
            days_before=days_before,
            send_sms=send_sms,
            send_email=send_email,
            sort_order=sort_order,
        )

    def _items_for(self, days_before):
        return get_due_notifications(today=self._day_for_rule(days_before))

    def _items_for_prescription(self, days_before):
        return [
            item for item in self._items_for(days_before)
            if item.get("prescription") == self.prescription
            and int(getattr(item.get("rule"), "days_before", -1)) == days_before
        ]

    def test_inactive_rule_is_ignored(self):
        self._create_rule(
            name="J-5 INACTIF",
            active=False,
            days_before=5,
            send_sms=True,
            send_email=True,
        )

        matched = self._items_for_prescription(5)

        self.assertEqual(matched, [])

    def test_sms_disabled_email_enabled(self):
        self._create_rule(
            name="J-5 EMAIL ONLY",
            active=True,
            days_before=5,
            send_sms=False,
            send_email=True,
        )

        matched = self._items_for_prescription(5)

        self.assertEqual(len(matched), 1)
        self.assertFalse(matched[0]["send_sms"])
        self.assertTrue(matched[0]["send_email"])

    def test_sms_enabled_email_disabled(self):
        self._create_rule(
            name="J-5 SMS ONLY",
            active=True,
            days_before=5,
            send_sms=True,
            send_email=False,
        )

        matched = self._items_for_prescription(5)

        self.assertEqual(len(matched), 1)
        self.assertTrue(matched[0]["send_sms"])
        self.assertFalse(matched[0]["send_email"])

    def test_changing_days_before_from_5_to_7_changes_detection_day(self):
        """
        Si le pharmacien transforme J-5 en J-7 :
        - le moteur doit détecter à J-7 ;
        - il ne doit plus détecter à J-5.
        """
        rule = self._create_rule(
            name="REGLE MODIFIABLE",
            active=True,
            days_before=5,
            send_sms=True,
            send_email=True,
        )

        matched_j5_before = self._items_for_prescription(5)
        self.assertEqual(len(matched_j5_before), 1)

        rule.days_before = 7
        rule.name = "J-7"
        rule.save(update_fields=["days_before", "name"])

        matched_j7_after = self._items_for_prescription(7)
        matched_j5_after = self._items_for_prescription(5)

        self.assertEqual(len(matched_j7_after), 1)
        self.assertEqual(matched_j5_after, [])
        self.assertEqual(getattr(matched_j7_after[0]["rule"], "days_before"), 7)

    def test_new_rule_j30_is_detected_without_code_change(self):
        self._create_rule(
            name="J-30",
            active=True,
            days_before=30,
            send_sms=True,
            send_email=True,
        )

        matched = self._items_for_prescription(30)

        self.assertEqual(len(matched), 1)
        self.assertEqual(getattr(matched[0]["rule"], "days_before"), 30)
        self.assertTrue(matched[0]["send_sms"])
        self.assertTrue(matched[0]["send_email"])

    def test_deleted_rule_no_longer_generates_notifications(self):
        rule = self._create_rule(
            name="J-10",
            active=True,
            days_before=10,
            send_sms=True,
            send_email=True,
        )

        self.assertEqual(len(self._items_for_prescription(10)), 1)

        rule.delete()

        self.assertEqual(self._items_for_prescription(10), [])

    def test_all_rules_disabled_returns_zero_notifications(self):
        for days in [21, 10, 5, 2, 30]:
            self._create_rule(
                name=f"J-{days} INACTIF",
                active=False,
                days_before=days,
                send_sms=True,
                send_email=True,
                sort_order=days,
            )

        for days in [21, 10, 5, 2, 30]:
            self.assertEqual(self._items_for_prescription(days), [])

    def test_multiple_dynamic_rules_are_all_detected_on_their_own_days(self):
        configured_days = [30, 15, 7, 1]

        for days in configured_days:
            self._create_rule(
                name=f"J-{days}",
                active=True,
                days_before=days,
                send_sms=True,
                send_email=True,
                sort_order=days,
            )

        for days in configured_days:
            matched = self._items_for_prescription(days)
            self.assertEqual(len(matched), 1)
            self.assertEqual(getattr(matched[0]["rule"], "days_before"), days)

    def test_two_rules_same_day_do_not_crash_and_return_two_rule_items(self):
        """
        Si le pharmacien crée deux règles le même jour,
        le moteur retourne deux entrées règle.
        L'envoi réel doit rester protégé par les marqueurs anti-doublon.
        """
        self._create_rule(
            name="J-5 SMS",
            active=True,
            days_before=5,
            send_sms=True,
            send_email=False,
            sort_order=1,
        )

        self._create_rule(
            name="J-5 EMAIL",
            active=True,
            days_before=5,
            send_sms=False,
            send_email=True,
            sort_order=2,
        )

        matched = self._items_for_prescription(5)

        self.assertEqual(len(matched), 2)

        sms_count = sum(1 for item in matched if item["send_sms"])
        email_count = sum(1 for item in matched if item["send_email"])

        self.assertEqual(sms_count, 1)
        self.assertEqual(email_count, 1)

    def test_already_sent_j5_rule_is_excluded(self):
        self._create_rule(
            name="J-5",
            active=True,
            days_before=5,
            send_sms=True,
            send_email=True,
        )

        self.assertEqual(len(self._items_for_prescription(5)), 1)

        now = timezone.now()
        self.cycle.reminder_5_patient_sms_sent_at = now
        self.cycle.reminder_5_patient_email_sent_at = now
        self.cycle.save(
            update_fields=[
                "reminder_5_patient_sms_sent_at",
                "reminder_5_patient_email_sent_at",
            ]
        )

        self.assertEqual(self._items_for_prescription(5), [])

    def test_already_sent_j1_rule_is_excluded(self):
        self._create_rule(
            name="J-1",
            active=True,
            days_before=1,
            send_sms=True,
            send_email=True,
        )

        self.assertEqual(len(self._items_for_prescription(1)), 1)

        now = timezone.now()
        self.cycle.reminder_1_patient_sms_sent_at = now
        self.cycle.reminder_1_patient_email_sent_at = now
        self.cycle.save(
            update_fields=[
                "reminder_1_patient_sms_sent_at",
                "reminder_1_patient_email_sent_at",
            ]
        )

        self.assertEqual(self._items_for_prescription(1), [])

    def test_management_command_dry_run_uses_dynamic_j30_rule(self):
        self._create_rule(
            name="J-30",
            active=True,
            days_before=30,
            send_sms=True,
            send_email=True,
        )

        out = StringIO()

        call_command(
            "run_renewal_notifications",
            date=str(self._day_for_rule(30)),
            stdout=out,
        )

        output = out.getvalue()

        self.assertIn("Mode : DRY-RUN", output)
        self.assertIn("Notifications à traiter : 1", output)
        self.assertIn("J-30", output)

        self.cycle.refresh_from_db()
        self.assertIsNone(self.cycle.reminder_5_patient_sms_sent_at)
        self.assertIsNone(self.cycle.reminder_5_patient_email_sent_at)

    def test_management_command_limit_one_limits_results(self):
        self._create_rule(
            name="J-5 A",
            active=True,
            days_before=5,
            send_sms=True,
            send_email=True,
            sort_order=1,
        )
        self._create_rule(
            name="J-5 B",
            active=True,
            days_before=5,
            send_sms=True,
            send_email=True,
            sort_order=2,
        )

        out = StringIO()

        call_command(
            "run_renewal_notifications",
            date=str(self._day_for_rule(5)),
            limit=1,
            stdout=out,
        )

        output = out.getvalue()

        self.assertIn("Notifications à traiter : 1", output)
        self.assertIn("processed: 1", output)
