"""Portal-owned e-learning models (not shared with ADMINISTRATION curriculum)."""

from django.db import models


class ELearningSubject(models.Model):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=40)
    description = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "portal_elearning_subject"
        ordering = ["display_order", "name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class ELearningEnrollment(models.Model):
    """Links a learner to an e-learning subject."""

    student_id = models.PositiveBigIntegerField(db_index=True)
    subject = models.ForeignKey(
        ELearningSubject,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "portal_elearning_enrollment"
        ordering = ["subject__display_order", "subject__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["student_id", "subject"],
                name="uniq_portal_elearning_student_subject",
            )
        ]

    def __str__(self):
        return f"student={self.student_id} · {self.subject_id}"
