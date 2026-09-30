# Generated manually — unmanaged mirror of ADMINISTRATION student conduct table.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0006_parentguardian_profile_image"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentConductRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("behaviour_type", models.CharField(choices=[("GOOD", "Good"), ("BAD", "Bad")], max_length=10)),
                ("description", models.TextField()),
                ("incident_date", models.DateField()),
                ("witness", models.CharField(max_length=200)),
                ("consequence_or_reward", models.TextField()),
                ("rating", models.PositiveSmallIntegerField()),
                ("created_at", models.DateTimeField()),
                ("updated_at", models.DateTimeField()),
                (
                    "student",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="conduct_records",
                        to="portal.student",
                    ),
                ),
            ],
            options={
                "db_table": "employees_studentconductrecord",
                "ordering": ["-incident_date", "-created_at"],
                "managed": False,
            },
        ),
    ]
