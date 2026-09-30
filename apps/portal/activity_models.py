"""
Read-only mirrors of ADMINISTRATION school activity / conduct tables.

managed = False — schema ownership stays with ADMINISTRATION.
"""

from django.db import models


class StudentConductRecord(models.Model):
    """A registered student behaviour incident (good or bad)."""

    class BehaviourType(models.TextChoices):
        GOOD = "GOOD", "Good"
        BAD = "BAD", "Bad"

    student = models.ForeignKey(
        "portal.Student",
        on_delete=models.DO_NOTHING,
        related_name="conduct_records",
        db_constraint=False,
    )
    behaviour_type = models.CharField(max_length=10, choices=BehaviourType.choices)
    description = models.TextField()
    incident_date = models.DateField()
    witness = models.CharField(max_length=200)
    consequence_or_reward = models.TextField()
    rating = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "employees_studentconductrecord"
        ordering = ["-incident_date", "-created_at"]

    def __str__(self):
        return f"{self.get_behaviour_type_display()} · {self.student_id} · {self.incident_date}"

    @property
    def rating_label(self):
        if self.behaviour_type == self.BehaviourType.BAD:
            return "Severity"
        return "Merit"

    @property
    def outcome_label(self):
        if self.behaviour_type == self.BehaviourType.BAD:
            return "Repercussion"
        return "Reward"


class SchoolActivity(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=12, default="PUBLISHED")
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "employees_schoolactivity"
        ordering = ["-updated_at", "-created_at"]

    def __str__(self):
        return self.title


class SchoolActivityDay(models.Model):
    activity = models.ForeignKey(
        SchoolActivity,
        on_delete=models.DO_NOTHING,
        related_name="days",
        db_constraint=False,
    )
    activity_date = models.DateField()
    day_description = models.CharField(max_length=255, blank=True)

    class Meta:
        managed = False
        db_table = "employees_schoolactivityday"
        ordering = ["activity_date", "id"]

    def __str__(self):
        return f"{self.activity_id}: {self.activity_date}"


class SchoolActivityGrade(models.Model):
    """Through table: which academic levels an activity applies to."""

    schoolactivity = models.ForeignKey(
        SchoolActivity,
        on_delete=models.DO_NOTHING,
        related_name="grade_links",
        db_constraint=False,
    )
    academiclevel = models.ForeignKey(
        "portal.AcademicLevel",
        on_delete=models.DO_NOTHING,
        related_name="school_activity_links",
        db_constraint=False,
    )

    class Meta:
        managed = False
        db_table = "employees_schoolactivity_grades"
