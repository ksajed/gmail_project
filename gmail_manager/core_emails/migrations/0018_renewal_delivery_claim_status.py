from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("core_emails", "0017_renewal_policy_j5_j1"),
    ]

    operations = [
        migrations.AddField(
            model_name="renewalnotificationdelivery",
            name="claimed_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name="renewalnotificationdelivery",
            name="failure_reason",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        migrations.AddField(
            model_name="renewalnotificationdelivery",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "En cours"),
                    ("SENT", "Envoyé"),
                    ("FAILED", "Échec"),
                ],
                default="SENT",
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="renewalnotificationdelivery",
            name="sent_at",
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
    ]
