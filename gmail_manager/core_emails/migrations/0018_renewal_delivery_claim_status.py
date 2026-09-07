from django.db import migrations, models
import django.utils.timezone


def ensure_delivery_table(apps, schema_editor):
    """Répare les bases ayant appliqué une ancienne variante de 0017.

    Pendant la revue de la PR, 0017 a d'abord été exécutée sans la table de
    livraison sur certains environnements de développement. Son état Django
    connaît désormais le modèle, mais la table physique peut manquer. Cette
    étape est sans effet sur une installation neuve et crée uniquement la
    table absente avant l'ajout des champs de réservation.
    """
    Delivery = apps.get_model("core_emails", "RenewalNotificationDelivery")
    table_names = schema_editor.connection.introspection.table_names()
    if Delivery._meta.db_table not in table_names:
        schema_editor.create_model(Delivery)


class Migration(migrations.Migration):
    dependencies = [
        ("core_emails", "0017_renewal_policy_j5_j1"),
    ]

    operations = [
        migrations.RunPython(
            ensure_delivery_table,
            migrations.RunPython.noop,
        ),
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
