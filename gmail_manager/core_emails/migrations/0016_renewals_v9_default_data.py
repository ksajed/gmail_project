# Generated manually for Ordo V9 renewals default configuration

from datetime import time
from django.db import migrations


def create_default_renewal_v9_data(apps, schema_editor):
    RenewalSettings = apps.get_model("core_emails", "RenewalSettings")
    RenewalNotificationRule = apps.get_model("core_emails", "RenewalNotificationRule")
    RenewalNotificationTemplate = apps.get_model("core_emails", "RenewalNotificationTemplate")

    if not RenewalSettings.objects.exists():
        RenewalSettings.objects.create(
            pharmacy_name="La Grande Pharmacie de Fives",
            phone="03 20 56 50 05",
            email="",
            opening_time=time(10, 0),
            closing_time=time(19, 0),
        )

    default_rules = [
        {
            "name": "J-21",
            "days_before": 21,
            "send_sms": True,
            "send_email": True,
            "active": True,
            "sort_order": 10,
        },
        {
            "name": "J-10",
            "days_before": 10,
            "send_sms": True,
            "send_email": False,
            "active": True,
            "sort_order": 20,
        },
        {
            "name": "J-5",
            "days_before": 5,
            "send_sms": True,
            "send_email": True,
            "active": True,
            "sort_order": 30,
        },
        {
            "name": "J-2",
            "days_before": 2,
            "send_sms": True,
            "send_email": False,
            "active": True,
            "sort_order": 40,
        },
    ]

    for rule in default_rules:
        RenewalNotificationRule.objects.get_or_create(
            days_before=rule["days_before"],
            defaults=rule,
        )

    RenewalNotificationTemplate.objects.get_or_create(
        name="SMS renouvellement standard",
        channel="SMS",
        defaults={
            "subject": "",
            "body": (
                "Bonjour,\\n"
                "Votre renouvellement approche.\\n"
                "Merci de contacter la pharmacie.\\n"
                "Référence : {numero_ordo}\\n"
                "{nom_pharmacie} - {telephone_pharmacie}"
            ),
            "active": True,
        },
    )

    RenewalNotificationTemplate.objects.get_or_create(
        name="Email renouvellement standard",
        channel="EMAIL",
        defaults={
            "subject": "Votre renouvellement approche",
            "body": (
                "Bonjour,\\n\\n"
                "Votre renouvellement approche.\\n"
                "Afin de préparer votre demande, merci de contacter la pharmacie.\\n\\n"
                "Référence : {numero_ordo}\\n"
                "{nom_pharmacie}\\n"
                "{telephone_pharmacie}"
            ),
            "active": True,
        },
    )


def reverse_default_renewal_v9_data(apps, schema_editor):
    RenewalSettings = apps.get_model("core_emails", "RenewalSettings")
    RenewalNotificationRule = apps.get_model("core_emails", "RenewalNotificationRule")
    RenewalNotificationTemplate = apps.get_model("core_emails", "RenewalNotificationTemplate")

    RenewalSettings.objects.filter(pharmacy_name="La Grande Pharmacie de Fives").delete()
    RenewalNotificationRule.objects.filter(days_before__in=[21, 10, 5, 2]).delete()
    RenewalNotificationTemplate.objects.filter(
        name__in=[
            "SMS renouvellement standard",
            "Email renouvellement standard",
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core_emails", "0015_renewalsettings_alter_prescription_status_and_more"),
    ]

    operations = [
        migrations.RunPython(
            create_default_renewal_v9_data,
            reverse_default_renewal_v9_data,
        ),
    ]
