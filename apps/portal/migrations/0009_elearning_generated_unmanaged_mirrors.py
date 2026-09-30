# Unmanaged mirrors for ADMINISTRATION grade-level e-learning tables.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0008_accounts_stk_unmanaged_mirrors"),
    ]

    operations = [
        migrations.CreateModel(
            name="GeneratedELearningTimetable",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField()),
            ],
            options={
                "db_table": "curriculum_generatedelearningtimetable",
                "ordering": ["-created_at"],
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="GeneratedELearningLesson",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("weekday", models.CharField(max_length=3)),
                ("period_name", models.CharField(max_length=120)),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                (
                    "academic_level",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="generated_elearning_lessons",
                        to="portal.academiclevel",
                    ),
                ),
                (
                    "generation",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="lessons",
                        to="portal.generatedelearningtimetable",
                    ),
                ),
                (
                    "learning_area",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="generated_elearning_lessons",
                        to="portal.learningarea",
                    ),
                ),
                (
                    "teacher",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="generated_elearning_lessons",
                        to="portal.employee",
                    ),
                ),
            ],
            options={
                "db_table": "curriculum_generatedelearninglesson",
                "ordering": ["weekday", "start_time"],
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="ELearningSubjectAllocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "academic_level",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="elearning_subject_allocations",
                        to="portal.academiclevel",
                    ),
                ),
                (
                    "learning_area",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="elearning_allocations",
                        to="portal.learningarea",
                    ),
                ),
                (
                    "teacher",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="elearning_subject_allocations",
                        to="portal.employee",
                    ),
                ),
            ],
            options={
                "db_table": "curriculum_elearningsubjectallocation",
                "ordering": [
                    "academic_level__order",
                    "learning_area__display_order",
                    "learning_area__name",
                ],
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="ELearningLearningMaterial",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("content_format", models.CharField(max_length=20)),
                ("category", models.CharField(max_length=120)),
                ("name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("cover_image", models.ImageField(blank=True, upload_to="elearning/materials/covers/%Y/%m/")),
                ("material_file", models.FileField(upload_to="elearning/materials/files/%Y/%m/")),
                ("original_filename", models.CharField(blank=True, max_length=255)),
                ("file_extension", models.CharField(blank=True, max_length=12)),
                ("file_size", models.PositiveBigIntegerField(default=0)),
                ("content_type", models.CharField(blank=True, max_length=120)),
                ("is_published", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField()),
                (
                    "allocation",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="learning_materials",
                        to="portal.elearningsubjectallocation",
                    ),
                ),
            ],
            options={
                "db_table": "curriculum_elearninglearningmaterial",
                "ordering": ["-created_at", "name"],
                "managed": False,
            },
        ),
    ]
