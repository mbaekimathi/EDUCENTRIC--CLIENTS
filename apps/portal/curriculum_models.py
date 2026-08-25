"""
Read-only mirrors of ADMINISTRATION curriculum tables used by the portal.

managed = False — schema ownership stays with ADMINISTRATION.
"""

from django.db import models


class AcademicLevel(models.Model):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=40)
    category = models.CharField(max_length=120)
    order = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, default="ACTIVE")

    class Meta:
        managed = False
        db_table = "curriculum_academiclevel"
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class AcademicClass(models.Model):
    academic_level = models.ForeignKey(
        AcademicLevel,
        on_delete=models.DO_NOTHING,
        related_name="classes",
        db_constraint=False,
    )
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=40)
    order = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, default="ACTIVE")

    class Meta:
        managed = False
        db_table = "curriculum_academicclass"
        ordering = ["academic_level", "order", "name"]

    def __str__(self):
        return f"{self.academic_level_id}: {self.name} ({self.code})"


class AcademicYear(models.Model):
    name = models.CharField(max_length=40)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    status = models.CharField(max_length=10, default="ACTIVE")

    class Meta:
        managed = False
        db_table = "curriculum_academicyear"
        ordering = ["-start_date", "name"]

    def __str__(self):
        return self.name


class AcademicTerm(models.Model):
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.DO_NOTHING,
        related_name="terms",
        db_constraint=False,
    )
    name = models.CharField(max_length=80)
    start_date = models.DateField()
    end_date = models.DateField()
    order = models.PositiveIntegerField(default=0)
    is_current = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = "curriculum_academicterm"
        ordering = ["academic_year", "order", "start_date"]

    def __str__(self):
        return f"{self.academic_year_id}: {self.name}"


class LearningArea(models.Model):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=40)
    total_marks = models.PositiveIntegerField(default=100)
    display_order = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, default="ACTIVE")

    class Meta:
        managed = False
        db_table = "curriculum_learningarea"
        ordering = ["display_order", "name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class ExamSubjectSetting(models.Model):
    academic_level = models.ForeignKey(
        AcademicLevel,
        on_delete=models.DO_NOTHING,
        related_name="exam_subject_settings",
        db_constraint=False,
    )
    learning_area = models.ForeignKey(
        LearningArea,
        on_delete=models.DO_NOTHING,
        related_name="exam_settings",
        db_constraint=False,
    )
    out_of_marks = models.PositiveIntegerField(default=100)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        managed = False
        db_table = "curriculum_examsubjectsetting"


class GradeBand(models.Model):
    academic_level = models.ForeignKey(
        AcademicLevel,
        on_delete=models.DO_NOTHING,
        related_name="grade_bands",
        null=True,
        blank=True,
        db_constraint=False,
    )
    code = models.CharField(max_length=20)
    mark_level = models.CharField(max_length=120)
    meaning = models.CharField(max_length=160)
    points = models.PositiveIntegerField(default=0)
    start_percent = models.PositiveIntegerField()
    end_percent = models.PositiveIntegerField()

    class Meta:
        managed = False
        db_table = "curriculum_gradeband"
        ordering = ["-end_percent", "-start_percent", "code"]


class Employee(models.Model):
    """Minimal mirror for teacher names on timetable lessons."""

    TITLE_LABELS = {
        "MR": "Mr.",
        "MRS": "Mrs.",
        "MISS": "Miss",
        "MS": "Ms.",
        "DR": "Dr.",
        "PROF": "Prof.",
    }

    title = models.CharField(max_length=10, blank=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)

    class Meta:
        managed = False
        db_table = "employees_employee"

    @property
    def title_label(self):
        raw = (self.title or "").strip().upper()
        if not raw:
            return ""
        return self.TITLE_LABELS.get(raw, raw.title())

    @property
    def display_name(self):
        parts = [self.title_label or self.title, self.first_name, self.last_name]
        return " ".join(p for p in parts if p).strip()

    @property
    def short_name(self):
        """Title + surname for compact timetable cells (e.g. Mr. Mbae)."""
        surname = (self.last_name or self.first_name or "").strip()
        if not surname:
            return self.title_label
        if self.title_label:
            return f"{self.title_label} {surname}"
        return surname


class GeneratedExamTimetable(models.Model):
    name = models.CharField(max_length=120, blank=True, default="")
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.DO_NOTHING,
        related_name="generated_exam_timetables",
        null=True,
        blank=True,
        db_constraint=False,
    )
    academic_term = models.ForeignKey(
        AcademicTerm,
        on_delete=models.DO_NOTHING,
        related_name="generated_exam_timetables",
        null=True,
        blank=True,
        db_constraint=False,
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "curriculum_generatedexamtimetable"
        ordering = ["-created_at"]

    @property
    def display_name(self):
        if self.name:
            return self.name
        if self.academic_year_id and self.academic_term_id:
            return f"{self.academic_year} · {self.academic_term.name}"
        return f"Exam {self.created_at:%Y-%m-%d}"


class ExamMark(models.Model):
    generation = models.ForeignKey(
        GeneratedExamTimetable,
        on_delete=models.DO_NOTHING,
        related_name="marks",
        db_constraint=False,
    )
    student = models.ForeignKey(
        "portal.Student",
        on_delete=models.DO_NOTHING,
        related_name="exam_marks",
        db_constraint=False,
    )
    learning_area = models.ForeignKey(
        LearningArea,
        on_delete=models.DO_NOTHING,
        related_name="exam_marks",
        db_constraint=False,
    )
    marks = models.PositiveIntegerField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "curriculum_exammark"
        ordering = ["learning_area__display_order", "learning_area__name"]


class ClassAttendanceSession(models.Model):
    academic_class = models.ForeignKey(
        AcademicClass,
        on_delete=models.DO_NOTHING,
        related_name="class_attendance_sessions",
        db_constraint=False,
    )
    attendance_date = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "curriculum_classattendancesession"
        ordering = ["-attendance_date"]


class ClassAttendanceRecord(models.Model):
    session = models.ForeignKey(
        ClassAttendanceSession,
        on_delete=models.DO_NOTHING,
        related_name="records",
        db_constraint=False,
    )
    student = models.ForeignKey(
        "portal.Student",
        on_delete=models.DO_NOTHING,
        related_name="class_attendance_records",
        db_constraint=False,
    )
    morning = models.BooleanField(default=False)
    afternoon = models.BooleanField(default=False)
    evening = models.BooleanField(default=False)
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "curriculum_classattendancerecord"
        ordering = ["-session__attendance_date"]


class GeneratedLearningTimetable(models.Model):
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "curriculum_generatedlearningtimetable"
        ordering = ["-created_at"]


class GeneratedLearningLesson(models.Model):
    generation = models.ForeignKey(
        GeneratedLearningTimetable,
        on_delete=models.DO_NOTHING,
        related_name="lessons",
        db_constraint=False,
    )
    academic_level = models.ForeignKey(
        AcademicLevel,
        on_delete=models.DO_NOTHING,
        related_name="generated_lessons",
        db_constraint=False,
    )
    academic_class = models.ForeignKey(
        AcademicClass,
        on_delete=models.DO_NOTHING,
        related_name="generated_lessons",
        db_constraint=False,
    )
    learning_area = models.ForeignKey(
        LearningArea,
        on_delete=models.DO_NOTHING,
        related_name="generated_lessons",
        db_constraint=False,
    )
    teacher = models.ForeignKey(
        Employee,
        on_delete=models.DO_NOTHING,
        related_name="generated_lessons",
        db_constraint=False,
    )
    weekday = models.CharField(max_length=3)
    period_name = models.CharField(max_length=120)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        managed = False
        db_table = "curriculum_generatedlearninglesson"
        ordering = ["weekday", "start_time"]
