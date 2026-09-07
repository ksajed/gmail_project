from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


# Les valeurs 10_000+ sont réservées à cette migration. Elles permettent au
# code inverse de distinguer les règles réellement modifiées ici des règles
# identiques que le pharmacien avait déjà désactivées ou créées lui-même.
MIGRATED_J21_SORT_ORDER = 10010
MIGRATED_J10_SORT_ORDER = 10020
MIGRATED_J2_SORT_ORDER = 10040


def apply_j5_j1_policy(apps, schema_editor):
    Rule = apps.get_model("core_emails", "RenewalNotificationRule")

    # Ne modifier que les règles initiales livrées par ORDO V9. Les règles
    # personnalisées du pharmacien restent intactes.
    Rule.objects.filter(
        name="J-21",
        days_before=21,
        send_sms=True,
        send_email=True,
        active=True,
        sort_order=10,
    ).update(
        active=False,
        sort_order=MIGRATED_J21_SORT_ORDER,
    )
    Rule.objects.filter(
        name="J-10",
        days_before=10,
        send_sms=True,
        send_email=False,
        active=True,
        sort_order=20,
    ).update(
        active=False,
        sort_order=MIGRATED_J10_SORT_ORDER,
    )

    default_j2 = Rule.objects.filter(
        name="J-2",
        days_before=2,
        send_sms=True,
        send_email=False,
        sort_order=40,
    ).first()
    if default_j2:
        Rule.objects.filter(pk=default_j2.pk).update(
            name="J-1",
            days_before=1,
            sort_order=MIGRATED_J2_SORT_ORDER,
        )


def reverse_j5_j1_policy(apps, schema_editor):
    """Restaure exactement la politique V9 remplacée par cette migration."""
    Rule = apps.get_model("core_emails", "RenewalNotificationRule")

    # Les ordres 10_000+ servent de marqueurs : une règle restée à son ordre
    # d'origine n'a pas été modifiée par apply_j5_j1_policy et doit donc rester
    # intacte, notamment si le pharmacien l'avait déjà désactivée.
    Rule.objects.filter(
        name="J-21",
        days_before=21,
        send_sms=True,
        send_email=True,
        active=False,
        sort_order=MIGRATED_J21_SORT_ORDER,
    ).update(active=True, sort_order=10)
    Rule.objects.filter(
        name="J-10",
        days_before=10,
        send_sms=True,
        send_email=False,
        active=False,
        sort_order=MIGRATED_J10_SORT_ORDER,
    ).update(active=True, sort_order=20)
    Rule.objects.filter(
        name="J-1",
        days_before=1,
        send_sms=True,
        send_email=False,
        sort_order=MIGRATED_J2_SORT_ORDER,
    ).update(
        name="J-2",
        days_before=2,
        sort_order=40,
    )


def backfill_legacy_delivery_markers(apps, schema_editor):
    """Associe les marqueurs historiques à leur unique règle par défaut."""
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
                    defaults={"sent_at": sent_at},
                )


class Migration(migrations.Migration):
    dependencies = [
        ("core_emails", "0016_renewals_v9_default_data"),
    ]

    operations = [
        migrations.AddField(
            model_name="prescriptionrenewalcycle",
            name="reminder_1_patient_email_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="prescriptionrenewalcycle",
            name="reminder_1_patient_sms_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="RenewalNotificationDelivery",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "channel",
                    models.CharField(
                        choices=[("SMS", "SMS"), ("EMAIL", "Email")],
                        max_length=10,
                    ),
                ),
                (
                    "sent_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                (
                    "cycle",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notification_deliveries",
                        to="core_emails.prescriptionrenewalcycle",
                    ),
                ),
                (
                    "rule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="deliveries",
                        to="core_emails.renewalnotificationrule",
                    ),
                ),
            ],
            options={"ordering": ["-sent_at"]},
        ),
        migrations.AddConstraint(
            model_name="renewalnotificationdelivery",
            constraint=models.UniqueConstraint(
                fields=("cycle", "rule", "channel"),
                name="uniq_renewal_delivery",
            ),
        ),
        migrations.RunPython(apply_j5_j1_policy, reverse_j5_j1_policy),
        migrations.RunPython(
            backfill_legacy_delivery_markers,
            migrations.RunPython.noop,
        ),
    ]
