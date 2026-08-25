# Portal-owned e-learning tables (managed by CLIENTS, not ADMINISTRATION).

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0003_finance_unmanaged_mirrors"),
    ]

    operations = [
        migrations.CreateModel(
            name="ELearningSubject",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("code", models.CharField(max_length=40)),
                ("description", models.TextField(blank=True)),
                ("display_order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "portal_elearning_subject",
                "ordering": ["display_order", "name"],
            },
        ),
        migrations.CreateModel(
            name="ELearningEnrollment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("student_id", models.PositiveBigIntegerField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "subject",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="enrollments",
                        to="portal.elearningsubject",
                    ),
                ),
            ],
            options={
                "db_table": "portal_elearning_enrollment",
                "ordering": ["subject__display_order", "subject__name"],
            },
        ),
        migrations.AddConstraint(
            model_name="elearningenrollment",
            constraint=models.UniqueConstraint(
                fields=("student_id", "subject"),
                name="uniq_portal_elearning_student_subject",
            ),
        ),
    ]
