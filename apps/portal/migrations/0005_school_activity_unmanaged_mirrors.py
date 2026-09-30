# Generated manually — unmanaged mirrors of ADMINISTRATION school activity tables.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0004_elearning"),
    ]

    operations = [
        migrations.CreateModel(
            name="SchoolActivity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(default="PUBLISHED", max_length=12)),
                ("created_at", models.DateTimeField()),
                ("updated_at", models.DateTimeField()),
            ],
            options={
                "db_table": "employees_schoolactivity",
                "ordering": ["-updated_at", "-created_at"],
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="SchoolActivityDay",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("activity_date", models.DateField()),
                ("day_description", models.CharField(blank=True, max_length=255)),
                (
                    "activity",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="days",
                        to="portal.schoolactivity",
                    ),
                ),
            ],
            options={
                "db_table": "employees_schoolactivityday",
                "ordering": ["activity_date", "id"],
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="SchoolActivityGrade",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "academiclevel",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="school_activity_links",
                        to="portal.academiclevel",
                    ),
                ),
                (
                    "schoolactivity",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="grade_links",
                        to="portal.schoolactivity",
                    ),
                ),
            ],
            options={
                "db_table": "employees_schoolactivity_grades",
                "managed": False,
            },
        ),
    ]
