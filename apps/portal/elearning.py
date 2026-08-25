"""E-learning helpers — portal-owned data only (no admin curriculum/timetable)."""

from __future__ import annotations

from .elearning_models import ELearningEnrollment, ELearningSubject
from .models import Student


def student_elearning_subjects(student: Student):
    subject_ids = (
        ELearningEnrollment.objects.filter(student_id=student.pk)
        .values_list("subject_id", flat=True)
        .distinct()
    )
    subjects = list(
        ELearningSubject.objects.filter(pk__in=subject_ids, is_active=True).order_by(
            "display_order", "name"
        )
    )
    return {"subjects": subjects}


def student_elearning_subject(student: Student, subject_id: int):
    enrolled = ELearningEnrollment.objects.filter(
        student_id=student.pk,
        subject_id=subject_id,
    ).exists()
    if not enrolled:
        return None
    subject = (
        ELearningSubject.objects.filter(pk=subject_id, is_active=True).first()
    )
    if subject is None:
        return None
    return {"subject": subject}
