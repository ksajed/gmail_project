from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core_emails", "0008_prescriptionrenewalevent"),
    ]

    operations = [
        migrations.AddField(
            model_name="prescriptionrenewalinfo",
            name="reminder_1_patient_email_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="prescriptionrenewalinfo",
            name="reminder_1_patient_sms_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="prescriptionrenewalinfo",
            name="overdue_patient_email_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="prescriptionrenewalinfo",
            name="overdue_patient_sms_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
