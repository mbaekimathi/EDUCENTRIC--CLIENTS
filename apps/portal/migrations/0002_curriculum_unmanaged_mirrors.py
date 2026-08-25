# Generated manually — unmanaged mirrors only (no schema changes).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0001_initial_unmanaged_mirrors"),
    ]

    operations = [
        migrations.CreateModel(
            name="AcademicLevel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("code", models.CharField(max_length=40)),
                ("category", models.CharField(max_length=120)),
                ("order", models.PositiveIntegerField(default=0)),
                ("status", models.CharField(default="ACTIVE", max_length=10)),
            ],
            options={
                "db_table": "curriculum_academiclevel",
                "ordering": ["order", "name"],
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="AcademicYear",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=40)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("is_current", models.BooleanField(default=False)),
                ("status", models.CharField(default="ACTIVE", max_length=10)),
            ],
            options={
                "db_table": "curriculum_academicyear",
                "ordering": ["-start_date", "name"],
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="Employee",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(blank=True, max_length=10)),
                ("first_name", models.CharField(max_length=150)),
                ("last_name", models.CharField(max_length=150)),
            ],
            options={
                "db_table": "employees_employee",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="GeneratedLearningTimetable",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField()),
            ],
            options={
                "db_table": "curriculum_generatedlearningtimetable",
                "ordering": ["-created_at"],
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="LearningArea",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("code", models.CharField(max_length=40)),
                ("total_marks", models.PositiveIntegerField(default=100)),
                ("display_order", models.PositiveIntegerField(default=0)),
                ("status", models.CharField(default="ACTIVE", max_length=10)),
            ],
            options={
                "db_table": "curriculum_learningarea",
                "ordering": ["display_order", "name"],
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="AcademicClass",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("code", models.CharField(max_length=40)),
                ("order", models.PositiveIntegerField(default=0)),
                ("status", models.CharField(default="ACTIVE", max_length=10)),
                (
                    "academic_level",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=models.deletion.DO_NOTHING,
                        related_name="classes",
                        to="portal.academiclevel",
                    ),
                ),
            ],
            options={
                "db_table": "curriculum_academicclass",
                "ordering": ["academic_level", "order", "name"],
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="AcademicTerm",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_current", models.BooleanField(default=False)),
                (
                    "academic_year",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=models.deletion.DO_NOTHING,
                        related_name="terms",
                        to="portal.academicyear",
                    ),
                ),
            ],
            options={
                "db_table": "curriculum_academicterm",
                "ordering": ["academic_year", "order", "start_date"],
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="ExamSubjectSetting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("out_of_marks", models.PositiveIntegerField(default=100)),
                ("display_order", models.PositiveIntegerField(default=0)),
                (
                    "academic_level",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=models.deletion.DO_NOTHING,
                        related_name="exam_subject_settings",
                        to="portal.academiclevel",
                    ),
                ),
                (
                    "learning_area",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=models.deletion.DO_NOTHING,
                        related_name="exam_settings",
                        to="portal.learningarea",
                    ),
                ),
            ],
            options={
                "db_table": "curriculum_examsubjectsetting",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="GradeBand",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=20)),
                ("mark_level", models.CharField(max_length=120)),
                ("meaning", models.CharField(max_length=160)),
                ("points", models.PositiveIntegerField(default=0)),
                ("start_percent", models.PositiveIntegerField()),
                ("end_percent", models.PositiveIntegerField()),
                (
                    "academic_level",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=models.deletion.DO_NOTHING,
                        related_name="grade_bands",
                        to="portal.academiclevel",
                    ),
                ),
            ],
            options={
                "db_table": "curriculum_gradeband",
                "ordering": ["-end_percent", "-start_percent", "code"],
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="GeneratedExamTimetable",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(blank=True, default="", max_length=120)),
                ("start_date", models.DateField(blank=True, null=True)),
                ("end_date", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField()),
                (
                    "academic_term",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=models.deletion.DO_NOTHING,
                        related_name="generated_exam_timetables",
                        to="portal.academicterm",
                    ),
                ),
                (
                    "academic_year",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=models.deletion.DO_NOTHING,
                        related_name="generated_exam_timetables",
                        to="portal.academicyear",
                    ),
                ),
            ],
            options={
                "db_table": "curriculum_generatedexamtimetable",
                "ordering": ["-created_at"],
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="ClassAttendanceSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("attendance_date", models.DateField()),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField()),
                ("updated_at", models.DateTimeField()),
                (
                    "academic_class",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=models.deletion.DO_NOTHING,
                        related_name="class_attendance_sessions",
                        to="portal.academicclass",
                    ),
                ),
            ],
            options={
                "db_table": "curriculum_classattendancesession",
                "ordering": ["-attendance_date"],
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="ClassAttendanceRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("morning", models.BooleanField(default=False)),
                ("afternoon", models.BooleanField(default=False)),
                ("evening", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField()),
                (
                    "session",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=models.deletion.DO_NOTHING,
                        related_name="records",
                        to="portal.classattendancesession",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=models.deletion.DO_NOTHING,
                        related_name="class_attendance_records",
                        to="portal.student",
                    ),
                ),
            ],
            options={
                "db_table": "curriculum_classattendancerecord",
                "ordering": ["-session__attendance_date"],
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="ExamMark",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("marks", models.PositiveIntegerField()),
                ("updated_at", models.DateTimeField()),
                (
                    "generation",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=models.deletion.DO_NOTHING,
                        related_name="marks",
                        to="portal.generatedexamtimetable",
                    ),
                ),
                (
                    "learning_area",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=models.deletion.DO_NOTHING,
                        related_name="exam_marks",
                        to="portal.learningarea",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=models.deletion.DO_NOTHING,
                        related_name="exam_marks",
                        to="portal.student",
                    ),
                ),
            ],
            options={
                "db_table": "curriculum_exammark",
                "ordering": ["learning_area__display_order", "learning_area__name"],
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="GeneratedLearningLesson",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("weekday", models.CharField(max_length=3)),
                ("period_name", models.CharField(max_length=120)),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                (
                    "academic_class",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=models.deletion.DO_NOTHING,
                        related_name="generated_lessons",
                        to="portal.academicclass",
                    ),
                ),
                (
                    "academic_level",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=models.deletion.DO_NOTHING,
                        related_name="generated_lessons",
                        to="portal.academiclevel",
                    ),
                ),
                (
                    "generation",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=models.deletion.DO_NOTHING,
                        related_name="lessons",
                        to="portal.generatedlearningtimetable",
                    ),
                ),
                (
                    "learning_area",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=models.deletion.DO_NOTHING,
                        related_name="generated_lessons",
                        to="portal.learningarea",
                    ),
                ),
                (
                    "teacher",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=models.deletion.DO_NOTHING,
                        related_name="generated_lessons",
                        to="portal.employee",
                    ),
                ),
            ],
            options={
                "db_table": "curriculum_generatedlearninglesson",
                "ordering": ["weekday", "start_time"],
                "managed": False,
            },
        ),
    ]
