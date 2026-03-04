from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core_people", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="person",
            name="is_active",
            field=models.BooleanField(default=True, help_text="Mandataire actif (désactivation = accès retiré)"),
        ),
    ]
