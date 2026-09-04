from __future__ import annotations

from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from django.utils import timezone

from core_emails.services_renewal_rules import (
    claim_rule_channel,
    get_due_notifications,
    mark_rule_channel_failed,
    mark_rule_channel_sent,
    renewal_sms_template_key,
)
from core_emails.services_renewal_templates import render_renewal_message


class Command(BaseCommand):
    help = "Exécute les notifications automatiques de renouvellement Ordo V9."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            dest="date",
            default=None,
            help="Date métier à tester/exécuter au format YYYY-MM-DD.",
        )
        parser.add_argument(
            "--limit",
            dest="limit",
            type=int,
            default=0,
            help="Nombre maximum de notifications à traiter. 0 = aucune limite.",
        )
        parser.add_argument(
            "--send",
            action="store_true",
            help="Envoie réellement les SMS/Emails. Sans cette option, dry-run.",
        )

    def handle(self, *args, **options):
        send_real = bool(options.get("send"))
        limit = int(options.get("limit") or 0)

        run_date = None
        if options.get("date"):
            run_date = parse_date(options["date"])
            if not run_date:
                self.stderr.write(self.style.ERROR("Date invalide. Format attendu : YYYY-MM-DD"))
                return

        notifications = list(get_due_notifications(today=run_date))

        if limit > 0:
            notifications = notifications[:limit]

        self.stdout.write("=== ORDO V9 RENEWAL NOTIFICATIONS ===")
        self.stdout.write(f"Mode : {'SEND' if send_real else 'DRY-RUN'}")
        self.stdout.write(f"Date : {run_date or timezone.localdate()}")
        self.stdout.write(f"Notifications à traiter : {len(notifications)}")

        summary = {
            "processed": 0,
            "sms_sent": 0,
            "email_sent": 0,
            "sms_skipped": 0,
            "email_skipped": 0,
            "errors": 0,
        }

        for item in notifications:
            summary["processed"] += 1

            prescription = item.get("prescription")
            cycle = item.get("cycle")
            rule = item.get("rule")
            due_date = item.get("due_date")

            pid = getattr(prescription, "id", None)
            cycle_number = getattr(cycle, "cycle_number", None)
            days_before = getattr(rule, "days_before", None)

            self.stdout.write("")
            self.stdout.write(
                f"- Prescription #{pid} | cycle {cycle_number} | J-{days_before} | échéance {due_date}"
            )

            # SMS
            if item.get("send_sms"):
                try:
                    result = self._handle_sms(
                        prescription=prescription,
                        cycle=cycle,
                        rule=rule,
                        due_date=due_date,
                        days_before=days_before,
                        send_real=send_real,
                    )
                    if result == "SENT":
                        summary["sms_sent"] += 1
                    elif self._is_skipped_result(result):
                        summary["sms_skipped"] += 1
                    else:
                        summary["errors"] += 1
                    self.stdout.write(f"  SMS : {result}")
                except Exception as e:
                    summary["errors"] += 1
                    self.stderr.write(f"  SMS ERROR : {type(e).__name__}: {e}")
            else:
                summary["sms_skipped"] += 1
                self.stdout.write("  SMS : SKIPPED(rule)")

            # EMAIL
            if item.get("send_email"):
                try:
                    result = self._handle_email(
                        prescription=prescription,
                        cycle=cycle,
                        rule=rule,
                        due_date=due_date,
                        days_before=days_before,
                        send_real=send_real,
                    )
                    if result == "SENT":
                        summary["email_sent"] += 1
                    elif self._is_skipped_result(result):
                        summary["email_skipped"] += 1
                    else:
                        summary["errors"] += 1
                    self.stdout.write(f"  EMAIL : {result}")
                except Exception as e:
                    summary["errors"] += 1
                    self.stderr.write(f"  EMAIL ERROR : {type(e).__name__}: {e}")
            else:
                summary["email_skipped"] += 1
                self.stdout.write("  EMAIL : SKIPPED(rule)")

        self.stdout.write("")
        self.stdout.write("=== RÉSUMÉ ===")
        for k, v in summary.items():
            self.stdout.write(f"{k}: {v}")

    @staticmethod
    def _is_skipped_result(result) -> bool:
        normalized = str(result or "").upper()
        return normalized == "DRY-RUN" or normalized.startswith("SKIPPED")

    def _safe_reference(self, prescription):
        return f"#{getattr(prescription, 'id', '')}"

    def _due_date_fr(self, due_date):
        try:
            return due_date.strftime("%d/%m/%Y")
        except Exception:
            return ""

    def _handle_sms(
        self,
        *,
        prescription,
        cycle,
        rule=None,
        due_date,
        days_before,
        send_real: bool,
    ):
        patient = getattr(prescription, "patient", None)
        phone = getattr(patient, "phone_number", None)

        if not phone:
            return "SKIPPED(no-phone)"

        _subject, body, template = render_renewal_message(
            "SMS",
            prescription,
            cycle=cycle,
            extra_context={
                "date_echeance": self._due_date_fr(due_date),
                "jours_avant": days_before,
            },
        )

        if not body:
            body = (
                f"Votre renouvellement approche. Référence : {self._safe_reference(prescription)}. "
                "Merci de contacter la pharmacie."
            )

        if not send_real:
            return "DRY-RUN"

        delivery_claim = None
        if rule is not None:
            delivery_claim = claim_rule_channel(cycle, rule, "SMS")
            if delivery_claim is None:
                return "SKIPPED(already-claimed)"

        from core_notifications.services import send_sms_logged
        from core_notifications.models import SmsPurpose, SmsStatus

        purpose = getattr(SmsPurpose, "RENEWAL", SmsPurpose.INFO)

        try:
            sms = send_sms_logged(
                to_e164=phone,
                text=body,
                purpose=purpose,
                template_key=renewal_sms_template_key(
                    getattr(template, "name", "") if template else "renewal_auto",
                    rule,
                ),
                prescription=prescription,
            )
        except Exception as exc:
            if delivery_claim is not None:
                mark_rule_channel_failed(
                    delivery_claim,
                    reason=f"{type(exc).__name__}: {exc}",
                )
            raise

        sms_status = getattr(sms, "status", None)
        if sms_status != SmsStatus.SENT:
            if delivery_claim is not None:
                mark_rule_channel_failed(
                    delivery_claim,
                    reason=str(sms_status or "FAILED"),
                )
            return str(sms_status or "FAILED")

        if rule is not None:
            mark_rule_channel_sent(cycle, rule, "SMS")

        return "SENT"

    def _handle_email(
        self,
        *,
        prescription,
        cycle,
        rule=None,
        due_date,
        days_before,
        send_real: bool,
    ):
        patient = getattr(prescription, "patient", None)
        email = getattr(patient, "email", None)

        if not email:
            return "SKIPPED(no-email)"

        subject, body, template = render_renewal_message(
            "EMAIL",
            prescription,
            cycle=cycle,
            extra_context={
                "date_echeance": self._due_date_fr(due_date),
                "jours_avant": days_before,
            },
        )

        if not subject:
            subject = "Votre renouvellement approche"

        if not body:
            body = "\n".join([
                "Bonjour,",
                "",
                f"Votre renouvellement approche. Référence : {self._safe_reference(prescription)}.",
                "Merci de contacter la pharmacie.",
                "",
                "Cordialement,",
                "La pharmacie",
            ])

        if not send_real:
            return "DRY-RUN"

        delivery_claim = None
        if rule is not None:
            delivery_claim = claim_rule_channel(cycle, rule, "EMAIL")
            if delivery_claim is None:
                return "SKIPPED(already-claimed)"

        from core_emails.services_notifications import _send_email_strict

        try:
            result = _send_email_strict(
                to_email=email,
                subject=subject,
                body=body,
            )
        except Exception as exc:
            if delivery_claim is not None:
                mark_rule_channel_failed(
                    delivery_claim,
                    reason=f"{type(exc).__name__}: {exc}",
                )
            raise

        if result == "SENT" and rule is not None:
            mark_rule_channel_sent(cycle, rule, "EMAIL")
        elif delivery_claim is not None:
            mark_rule_channel_failed(delivery_claim, reason=str(result or "FAILED"))

        return result
