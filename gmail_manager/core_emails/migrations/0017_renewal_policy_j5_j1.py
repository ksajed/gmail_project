from django.db import migrations, models


def apply_j5_j1_policy(apps, schema_editor):
    Rule = apps.get_model("core_emails", "RenewalNotificationRule")

    # Ne modifier que les règles initiales livrées par ORDO V9. Les règles
    # personnalisées du pharmacien restent intactes.
    Rule.objects.filter(name="J-21", days_before=21, sort_order=10).update(active=False)
    Rule.objects.filter(name="J-10", days_before=10, sort_order=20).update(active=False)

    default_j2 = Rule.objects.filter(name="J-2", days_before=2, sort_order=40).first()
    if default_j2:
        Rule.objects.filter(pk=default_j2.pk).update(
            name="J-1",
            days_before=1,
            active=True,
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
        # Ne pas tenter de restaurer automatiquement une configuration qui a
        # pu être personnalisée après la migration.
        migrations.RunPython(apply_j5_j1_policy, migrations.RunPython.noop),
    ]
