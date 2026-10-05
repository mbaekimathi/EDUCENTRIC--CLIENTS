"""E-learning helpers — grade-level generated timetable (class branches share one grade)."""

from __future__ import annotations

from datetime import date, timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, OperationalError, transaction
from django.utils import timezone

from .curriculum_models import (
    ELearningAttendanceRecord,
    ELearningAttendanceSession,
    ELearningLearningMaterial,
    ELearningSubjectAllocation,
    GeneratedELearningLesson,
    LearningArea,
)
from .models import Student
from .student_records import (
    DAY_ORDER,
    WEEKDAY_LABELS,
    _student_level_choice,
    academic_level_for_student,
)


class ElearningAttendanceBusy(Exception):
    """Another save is in progress or the grade register is too large."""


def _elearning_attendance_lock_key(allocation_id: int, lesson_date: date) -> str:
    return f"elearning_att:{allocation_id}:{lesson_date.isoformat()}"


def _elearning_learner_cap() -> int:
    return getattr(settings, "PORTAL_ELEARNING_ATTENDANCE_MAX_LEARNERS", 600)


def _elearning_lock_seconds() -> int:
    return getattr(settings, "PORTAL_ELEARNING_ATTENDANCE_LOCK_SECONDS", 75)


def elearning_attendance_grade_size(level) -> int:
    return len(students_for_elearning_level(level))


def _latest_generation_id_for_level(level_id: int) -> int | None:
    return (
        GeneratedELearningLesson.objects.filter(academic_level_id=level_id)
        .order_by("-generation_id")
        .values_list("generation_id", flat=True)
        .first()
    )


def _lessons_for_level(level_id: int) -> list[GeneratedELearningLesson]:
    generation_id = _latest_generation_id_for_level(level_id)
    if generation_id is None:
        return []
    return list(
        GeneratedELearningLesson.objects.filter(
            academic_level_id=level_id,
            generation_id=generation_id,
        )
        .select_related("learning_area", "teacher", "academic_level")
        .order_by("weekday", "start_time", "period_name")
    )


def _subjects_from_lessons(lessons: list[GeneratedELearningLesson]) -> list[LearningArea]:
    seen: dict[int, LearningArea] = {}
    for lesson in lessons:
        area = lesson.learning_area
        if area is None or area.pk in seen:
            continue
        seen[area.pk] = area
    subjects = list(seen.values())
    subjects.sort(key=lambda area: (area.display_order, area.name))
    return subjects


def _build_timetable_grid(lessons: list[GeneratedELearningLesson]) -> dict:
    if not lessons:
        return {"days": [], "day_labels": WEEKDAY_LABELS, "periods": [], "rows": []}

    days = [day for day in DAY_ORDER if any(item.weekday == day for item in lessons)]
    periods: list[dict] = []
    seen = set()
    for lesson in sorted(lessons, key=lambda item: (item.start_time, item.end_time, item.period_name)):
        key = (lesson.period_name, lesson.start_time, lesson.end_time)
        if key in seen:
            continue
        seen.add(key)
        periods.append(
            {
                "name": lesson.period_name,
                "start": lesson.start_time,
                "end": lesson.end_time,
            }
        )

    grid: dict[tuple, GeneratedELearningLesson] = {}
    for lesson in lessons:
        key = (lesson.weekday, lesson.period_name, lesson.start_time, lesson.end_time)
        grid[key] = lesson

    rows = []
    for day in days:
        cells = [
            grid.get((day, period["name"], period["start"], period["end"]))
            for period in periods
        ]
        rows.append(
            {
                "code": day,
                "label": WEEKDAY_LABELS.get(day, day),
                "cells": cells,
            }
        )

    return {
        "days": days,
        "day_labels": WEEKDAY_LABELS,
        "periods": periods,
        "rows": rows,
    }


def student_elearning_subjects(student: Student):
    """Grade e-learning timetable + subjects (all class streams share the grade)."""
    level = academic_level_for_student(student)
    if level is None:
        return {
            "academic_level": None,
            "subjects": [],
            "lesson_count": 0,
            "days": [],
            "day_labels": WEEKDAY_LABELS,
            "periods": [],
            "rows": [],
        }

    lessons = _lessons_for_level(level.pk)
    subjects = _subjects_from_lessons(lessons)
    if not subjects:
        # Fall back to allocated subjects for the grade when timetable is empty.
        subjects = [
            allocation.learning_area
            for allocation in ELearningSubjectAllocation.objects.filter(
                academic_level_id=level.pk
            )
            .select_related("learning_area")
            .order_by("learning_area__display_order", "learning_area__name")
        ]

    return {
        "academic_level": level,
        "subjects": subjects,
        "lesson_count": len(lessons),
        **_build_timetable_grid(lessons),
    }


def student_elearning_count(student: Student) -> int:
    level = academic_level_for_student(student)
    if level is None:
        return 0
    lessons = _lessons_for_level(level.pk)
    if lessons:
        return len({lesson.learning_area_id for lesson in lessons})
    return (
        ELearningSubjectAllocation.objects.filter(academic_level_id=level.pk)
        .values("learning_area_id")
        .distinct()
        .count()
    )


def student_elearning_subject(student: Student, subject_id: int):
    level = academic_level_for_student(student)
    if level is None:
        return None

    allocation = (
        ELearningSubjectAllocation.objects.filter(
            academic_level_id=level.pk,
            learning_area_id=subject_id,
        )
        .select_related("learning_area", "teacher", "academic_level")
        .first()
    )

    on_timetable = GeneratedELearningLesson.objects.filter(
        academic_level_id=level.pk,
        learning_area_id=subject_id,
        generation_id=_latest_generation_id_for_level(level.pk) or 0,
    ).exists()

    if allocation is None and not on_timetable:
        return None

    subject = (
        allocation.learning_area
        if allocation is not None
        else LearningArea.objects.filter(pk=subject_id).first()
    )
    if subject is None:
        return None

    materials = []
    sessions = []
    materials_truncated = False
    materials_limit = getattr(settings, "PORTAL_ELEARNING_MATERIALS_MAX", 100)
    if allocation is not None:
        material_batch = list(
            ELearningLearningMaterial.objects.filter(
                allocation_id=allocation.pk,
                is_published=True,
            ).order_by("-created_at", "name")[: materials_limit + 1]
        )
        materials_truncated = len(material_batch) > materials_limit
        materials = material_batch[:materials_limit]
    generation_id = _latest_generation_id_for_level(level.pk)
    if generation_id is not None:
        for lesson in GeneratedELearningLesson.objects.filter(
            academic_level_id=level.pk,
            learning_area_id=subject_id,
            generation_id=generation_id,
        ).select_related("teacher").order_by("weekday", "start_time"):
            sessions.append(
                {
                    "weekday": lesson.weekday,
                    "day_label": WEEKDAY_LABELS.get(lesson.weekday, lesson.weekday),
                    "period_name": lesson.period_name,
                    "start_time": lesson.start_time,
                    "end_time": lesson.end_time,
                    "teacher": lesson.teacher,
                    "teacher_id": lesson.teacher_id,
                }
            )

    return {
        "academic_level": level,
        "subject": subject,
        "allocation": allocation,
        "materials": materials,
        "materials_truncated": materials_truncated,
        "materials_limit": materials_limit,
        "sessions": sessions,
    }


def students_for_elearning_level(level) -> list[Student]:
    """Active learners on the same academic grade (all class streams)."""
    if level is None:
        return []
    choice = _student_level_choice(level)
    if not choice:
        return []
    return list(
        Student.objects.filter(
            academic_level=choice,
            is_active=True,
            is_suspended=False,
        ).order_by("last_name", "first_name", "assessment_number")
    )


def parse_lesson_date(raw: str | None) -> date:
    value = (raw or "").strip()
    if not value:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError:
        return date.today()


def parse_calendar_month(raw: str | None, fallback: date) -> date:
    """Return the first day of the month to display in the attendance calendar."""
    value = (raw or "").strip()
    if value:
        try:
            year_s, month_s = value.split("-", 1)
            year, month = int(year_s), int(month_s)
            if 1 <= month <= 12:
                return date(year, month, 1)
        except (TypeError, ValueError):
            pass
    return date(fallback.year, fallback.month, 1)


def attendance_taken_dates(allocation, start: date, end: date) -> set[date]:
    if allocation is None:
        return set()
    return set(
        ELearningAttendanceSession.objects.filter(
            allocation_id=allocation.pk,
            lesson_date__gte=start,
            lesson_date__lte=end,
        ).values_list("lesson_date", flat=True)
    )


def attendance_month_calendar(allocation, calendar_month: date, selected: date):
    """Build a Monday-start month grid with taken / selected / today flags."""
    import calendar as pycal

    year, month = calendar_month.year, calendar_month.month
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year, 12, 31)
        next_month = date(year + 1, 1, 1)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)
        next_month = date(year, month + 1, 1)
    prev_month = date(year - 1, 12, 1) if month == 1 else date(year, month - 1, 1)

    # Pad to full weeks for adjacent-month day markers.
    first_weekday = month_start.weekday()  # Monday=0
    grid_start = month_start - timedelta(days=first_weekday)
    last_weekday = month_end.weekday()
    grid_end = month_end + timedelta(days=(6 - last_weekday))

    taken = attendance_taken_dates(allocation, grid_start, grid_end)
    today = date.today()
    weeks = []
    cursor = grid_start
    while cursor <= grid_end:
        week = []
        for _ in range(7):
            iso = cursor.isoformat()
            week.append(
                {
                    "date": cursor,
                    "iso": iso,
                    "day": cursor.day,
                    "in_month": cursor.month == month,
                    "is_today": cursor == today,
                    "is_selected": cursor == selected,
                    "is_taken": cursor in taken,
                }
            )
            cursor += timedelta(days=1)
        weeks.append(week)

    return {
        "calendar_month": month_start,
        "calendar_label": month_start.strftime("%B %Y"),
        "calendar_weeks": weeks,
        "calendar_prev": prev_month.strftime("%Y-%m"),
        "calendar_next": next_month.strftime("%Y-%m"),
        "calendar_weekday_labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "taken_in_month_count": sum(
            1 for day in taken if day.month == month and day.year == year
        ),
        "days_in_month": pycal.monthrange(year, month)[1],
    }


def subject_attendance_roll(allocation, level, lesson_date: date, calendar_month: date | None = None):
    """Students + statuses for one e-learning subject attendance day."""
    students = students_for_elearning_level(level)
    session = None
    status_lookup: dict[int, str] = {}
    if allocation is not None:
        session = (
            ELearningAttendanceSession.objects.filter(
                allocation_id=allocation.pk,
                lesson_date=lesson_date,
            ).first()
        )
        if session is not None:
            status_lookup = {
                record.student_id: record.status
                for record in ELearningAttendanceRecord.objects.filter(session_id=session.pk)
            }

    roll = []
    for learner in students:
        raw = status_lookup.get(learner.pk, ELearningAttendanceRecord.Status.PRESENT)
        # Portal UI is binary present/absent.
        status = (
            ELearningAttendanceRecord.Status.PRESENT
            if raw == ELearningAttendanceRecord.Status.PRESENT
            else ELearningAttendanceRecord.Status.ABSENT
        )
        roll.append({"student": learner, "status": status})

    present_count = sum(
        1 for row in roll if row["status"] == ELearningAttendanceRecord.Status.PRESENT
    )
    absent_count = len(roll) - present_count
    focus_month = calendar_month or date(lesson_date.year, lesson_date.month, 1)

    return {
        "lesson_date": lesson_date,
        "attendance_session": session,
        "attendance_taken": session is not None,
        "attendance_roll": roll,
        "present_count": present_count,
        "absent_count": absent_count,
        "can_mark_attendance": allocation is not None,
        **attendance_month_calendar(allocation, focus_month, lesson_date),
    }


@transaction.atomic
def save_subject_attendance(allocation, level, lesson_date: date, notes: str, status_by_student: dict[int, str]):
    """Create/update the day's session and one record per learner on the grade."""
    students = students_for_elearning_level(level)
    cap = _elearning_learner_cap()
    if len(students) > cap:
        raise ElearningAttendanceBusy(
            f"This grade has too many learners ({len(students)}) to save in one request. "
            "Ask the school to split the register or try again later."
        )

    lock_key = _elearning_attendance_lock_key(allocation.pk, lesson_date)
    if not cache.add(lock_key, 1, _elearning_lock_seconds()):
        raise ElearningAttendanceBusy(
            "Another attendance save is in progress for this subject and date. "
            "Wait a moment and try again."
        )

    now = timezone.now()
    try:
        return _save_subject_attendance_locked(
            allocation,
            level,
            lesson_date,
            notes,
            status_by_student,
            students,
            now,
        )
    except (OperationalError, DatabaseError) as exc:
        raise ElearningAttendanceBusy(
            "The server is busy saving attendance. Wait a moment and try again."
        ) from exc
    finally:
        cache.delete(lock_key)


def _save_subject_attendance_locked(
    allocation,
    level,
    lesson_date: date,
    notes: str,
    status_by_student: dict[int, str],
    students: list[Student],
    now,
):
    session, created = ELearningAttendanceSession.objects.get_or_create(
        allocation_id=allocation.pk,
        lesson_date=lesson_date,
        defaults={
            "notes": notes,
            "taken_by_id": None,
            "created_at": now,
            "updated_at": now,
        },
    )
    if not created:
        session.notes = notes
        session.updated_at = now
        session.save(update_fields=["notes", "updated_at"])

    student_ids = {learner.pk for learner in students}
    allowed_ids = set(status_by_student.keys()) & student_ids
    status_by_student = {sid: status_by_student[sid] for sid in allowed_ids}
    existing = {
        record.student_id: record
        for record in ELearningAttendanceRecord.objects.filter(session_id=session.pk)
    }

    to_create = []
    to_update = []
    for learner in students:
        raw = (status_by_student.get(learner.pk) or "").strip().upper()
        status = (
            ELearningAttendanceRecord.Status.PRESENT
            if raw == ELearningAttendanceRecord.Status.PRESENT
            else ELearningAttendanceRecord.Status.ABSENT
        )
        current = existing.get(learner.pk)
        if current is None:
            to_create.append(
                ELearningAttendanceRecord(
                    session_id=session.pk,
                    student_id=learner.pk,
                    status=status,
                    updated_at=now,
                )
            )
        elif current.status != status:
            current.status = status
            current.updated_at = now
            to_update.append(current)

    if to_create:
        ELearningAttendanceRecord.objects.bulk_create(to_create)
    if to_update:
        ELearningAttendanceRecord.objects.bulk_update(to_update, ["status", "updated_at"])

    ELearningAttendanceRecord.objects.filter(session_id=session.pk).exclude(
        student_id__in=student_ids
    ).delete()
    return session

