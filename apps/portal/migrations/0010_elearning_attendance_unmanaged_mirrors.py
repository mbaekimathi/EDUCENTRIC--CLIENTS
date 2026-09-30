# Unmanaged mirrors for ADMINISTRATION e-learning attendance tables.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0009_elearning_generated_unmanaged_mirrors"),
    ]

    operations = [
        migrations.CreateModel(
            name="ELearningAttendanceSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("lesson_date", models.DateField()),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField()),
                ("updated_at", models.DateTimeField()),
                (
                    "allocation",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="attendance_sessions",
                        to="portal.elearningsubjectallocation",
                    ),
                ),
                (
                    "taken_by",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="elearning_attendance_sessions",
                        to="portal.employee",
                    ),
                ),
            ],
            options={
                "db_table": "curriculum_elearningattendancesession",
                "ordering": ["-lesson_date", "-updated_at"],
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="ELearningAttendanceRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(default="PRESENT", max_length=10)),
                ("updated_at", models.DateTimeField()),
                (
                    "session",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="records",
                        to="portal.elearningattendancesession",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="elearning_attendance_records",
                        to="portal.student",
                    ),
                ),
            ],
            options={
                "db_table": "curriculum_elearningattendancerecord",
                "ordering": ["student__last_name", "student__first_name"],
                "managed": False,
            },
        ),
    ]
