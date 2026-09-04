from django.db import migrations


def backfill_legacy_delivery_markers(apps, schema_editor):
    """Convertit les marqueurs historiques en livraisons opposables.

    Cette migration séparée s'exécute aussi sur les bases de revue ayant déjà
    appliqué 0018 avant l'ajout de ce rattrapage. L'opération est idempotente.
    """
    Rule = apps.get_model("core_emails", "RenewalNotificationRule")
    Cycle = apps.get_model("core_emails", "PrescriptionRenewalCycle")
    Delivery = apps.get_model("core_emails", "RenewalNotificationDelivery")

    default_rules = [
        (
            {"name": "J-5", "days_before": 5, "sort_order": 30},
            {
                "EMAIL": "reminder_5_patient_email_sent_at",
                "SMS": "reminder_5_patient_sms_sent_at",
            },
        ),
        (
            {"name": "J-3", "days_before": 3, "sort_order": 40},
            {
                "EMAIL": "reminder_3_patient_email_sent_at",
                "SMS": "reminder_3_patient_sms_sent_at",
            },
        ),
        (
            {"name": "J-1", "days_before": 1, "sort_order": 40},
            {
                "EMAIL": "reminder_1_patient_email_sent_at",
                "SMS": "reminder_1_patient_sms_sent_at",
            },
        ),
    ]

    for rule_signature, channel_fields in default_rules:
        matching_rules = list(
            Rule.objects.filter(**rule_signature).values_list("pk", flat=True)[:2]
        )
        if len(matching_rules) != 1:
            continue

        rule_id = matching_rules[0]
        for channel, field_name in channel_fields.items():
            marked_cycles = (
                Cycle.objects.exclude(**{f"{field_name}__isnull": True})
                .values_list("pk", field_name)
                .iterator()
            )
            for cycle_id, sent_at in marked_cycles:
                Delivery.objects.get_or_create(
                    cycle_id=cycle_id,
                    rule_id=rule_id,
                    channel=channel,
                    defaults={
                        "status": "SENT",
                        "claimed_at": sent_at,
                        "sent_at": sent_at,
                        "failure_reason": "",
                    },
                )


class Migration(migrations.Migration):
    dependencies = [
        ("core_emails", "0018_renewal_delivery_claim_status"),
    ]

    operations = [
        migrations.RunPython(
            backfill_legacy_delivery_markers,
            migrations.RunPython.noop,
        ),
    ]
