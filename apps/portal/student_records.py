"""Helpers to load attendance, exam results, timetable, and conduct for a portal student."""

from __future__ import annotations

import re
from collections import OrderedDict

from django.conf import settings
from django.core.cache import cache

from .activity_models import StudentConductRecord
from .curriculum_models import (
    AcademicClass,
    AcademicLevel,
    ClassAttendanceRecord,
    ExamMark,
    ExamSubjectSetting,
    GeneratedLearningLesson,
    GradeBand,
)
from .models import Student

DAY_ORDER = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
WEEKDAY_LABELS = {
    "MON": "Monday",
    "TUE": "Tuesday",
    "WED": "Wednesday",
    "THU": "Thursday",
    "FRI": "Friday",
    "SAT": "Saturday",
    "SUN": "Sunday",
}

_LEVELS_CACHE_KEY = "portal:active_academic_levels:v1"
_BANDS_CACHE_KEY = "portal:grade_bands:v1"
_LOOKUP_CACHE_TTL = 300


def _student_level_choice(level: AcademicLevel) -> str:
    name = (level.name or "").strip()
    for value, label in Student.AcademicLevel.choices:
        if label.casefold() == name.casefold():
            return value
        if value.replace("_", " ").casefold() == name.casefold():
            return value
    return ""


def _active_academic_levels() -> list[AcademicLevel]:
    levels = cache.get(_LEVELS_CACHE_KEY)
    if levels is None:
        levels = list(AcademicLevel.objects.filter(status="ACTIVE"))
        cache.set(_LEVELS_CACHE_KEY, levels, _LOOKUP_CACHE_TTL)
    return levels


def academic_level_for_student(student: Student) -> AcademicLevel | None:
    target = student.academic_level
    for level in _active_academic_levels():
        if _student_level_choice(level) == target:
            return level
    return None


def _class_group_values(academic_class: AcademicClass) -> set[str]:
    name = (academic_class.name or "").strip()
    code = (academic_class.code or "").strip()
    level = academic_class.academic_level
    level_code = (level.code or "").strip()
    level_name = (level.name or "").strip()
    values = {name, code, level_name}

    def compact(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9]", "", value or "")

    values.update({compact(name), compact(code), compact(level_code)})
    stripped_code = re.match(r"^[A-Za-z]*(\d+.*)$", code)
    if stripped_code:
        values.add(stripped_code.group(1))
    level_digits = re.search(r"(\d+)", level_code) or re.search(r"(\d+)", level_name)
    stream = compact(name)
    if level_digits and stream and not re.search(level_digits.group(1), stream):
        values.add(f"{level_digits.group(1)}{stream}")
        values.add(f"{level_digits.group(1)} {name}")
    return {value for value in values if value}


def academic_class_for_student(
    student: Student,
    level: AcademicLevel | None = None,
) -> AcademicClass | None:
    cache_key = f"portal:aclass:{student.pk}"
    if level is None:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached or None

    if level is None:
        level = academic_level_for_student(student)
    if level is None:
        cache.set(cache_key, False, 120)
        return None
    classes = list(
        AcademicClass.objects.filter(academic_level=level, status="ACTIVE")
        .select_related("academic_level")
        .order_by("order", "name")
    )
    if not classes:
        cache.set(cache_key, False, 120)
        return None

    resolved = None
    raw = (student.class_group or "").strip()
    if raw:
        for academic_class in classes:
            values = _class_group_values(academic_class)
            if any(raw.casefold() == value.casefold() for value in values):
                resolved = academic_class
                break

    if resolved is None and len(classes) == 1:
        resolved = classes[0]

    cache.set(cache_key, resolved if resolved is not None else False, 120)
    return resolved


def _all_grade_bands() -> list[GradeBand]:
    bands = cache.get(_BANDS_CACHE_KEY)
    if bands is None:
        bands = list(GradeBand.objects.select_related("academic_level").all())
        cache.set(_BANDS_CACHE_KEY, bands, _LOOKUP_CACHE_TTL)
    return bands


def _bands_for_level(level: AcademicLevel | None) -> list[GradeBand]:
    bands = _all_grade_bands()
    if level is not None:
        level_bands = [band for band in bands if band.academic_level_id == level.pk]
        if level_bands:
            return level_bands
    return [band for band in bands if band.academic_level_id is None]


def _grade_for_percent(
    percent: int | None,
    level: AcademicLevel | None,
    bands: list[GradeBand] | None = None,
) -> GradeBand | None:
    if percent is None:
        return None
    if bands is None:
        bands = _bands_for_level(level)
    for band in bands:
        if band.start_percent <= percent <= band.end_percent:
            return band
    return None


def student_attendance(
    student: Student,
    limit: int | None = None,
    *,
    include_class: bool = True,
    academic_class: AcademicClass | None = None,
):
    if limit is None:
        limit = getattr(settings, "PORTAL_ATTENDANCE_MAX_DAYS", 90)
    fetched = list(
        ClassAttendanceRecord.objects.filter(student=student)
        .select_related("session", "session__academic_class")
        .order_by("-session__attendance_date", "-updated_at")[: limit + 1]
    )
    history_truncated = len(fetched) > limit
    records = fetched[:limit]
    total_slots = 0
    present_slots = 0
    for record in records:
        for flag in (record.morning, record.afternoon, record.evening):
            total_slots += 1
            if flag:
                present_slots += 1
    rate = round((present_slots * 100) / total_slots) if total_slots else None
    resolved_class = academic_class
    if include_class and resolved_class is None:
        resolved_class = academic_class_for_student(student)
    return {
        "records": records,
        "days_recorded": len(records),
        "present_slots": present_slots,
        "total_slots": total_slots,
        "attendance_rate": rate,
        "academic_class": resolved_class if include_class else None,
        "history_truncated": history_truncated,
        "history_limit": limit,
    }


def _build_exam_list(
    student: Student,
    *,
    level: AcademicLevel | None,
    marks: list[ExamMark],
    bands: list[GradeBand],
) -> list[dict]:
    out_of_by_area: dict[int, int] = {}
    if level is not None:
        for setting in ExamSubjectSetting.objects.filter(academic_level=level).only(
            "learning_area_id", "out_of_marks"
        ):
            out_of_by_area[setting.learning_area_id] = setting.out_of_marks

    exams: OrderedDict[int, dict] = OrderedDict()
    for mark in marks:
        exam = exams.setdefault(
            mark.generation_id,
            {
                "generation": mark.generation,
                "rows": [],
                "total_percent": 0,
                "scored_subjects": 0,
            },
        )
        out_of = out_of_by_area.get(mark.learning_area_id) or mark.learning_area.total_marks or 100
        # Marks are often stored on the learning-area scale (e.g. 100) even when a
        # paper setting lists a smaller out_of — don't inflate percentages.
        area_total = mark.learning_area.total_marks or 100
        if mark.marks > out_of:
            out_of = area_total if area_total >= mark.marks else max(out_of, mark.marks)
        percent = round((mark.marks * 100) / out_of) if out_of else None
        grade = _grade_for_percent(percent, level, bands)
        exam["rows"].append(
            {
                "subject": mark.learning_area,
                "marks": mark.marks,
                "out_of": out_of,
                "percent": percent,
                "grade": grade,
            }
        )
        if percent is not None:
            exam["total_percent"] += percent
            exam["scored_subjects"] += 1

    exam_list = []
    for exam in exams.values():
        avg = (
            round(exam["total_percent"] / exam["scored_subjects"])
            if exam["scored_subjects"]
            else None
        )
        exam_list.append(
            {
                "generation": exam["generation"],
                "rows": exam["rows"],
                "average_percent": avg,
                "average_grade": _grade_for_percent(avg, level, bands),
            }
        )
    return exam_list


def student_results(student: Student, *, max_exams: int | None = None):
    """Load exam marks. Caps to the newest ``max_exams`` generations (None = all)."""
    if max_exams is None:
        max_exams = getattr(settings, "PORTAL_RESULTS_MAX_EXAMS", 12)
    level = academic_level_for_student(student)
    bands = _bands_for_level(level)

    from django.db.models import Max

    total_exam_count = (
        ExamMark.objects.filter(student=student)
        .values("generation_id")
        .distinct()
        .count()
    )
    exams_truncated = max_exams is not None and total_exam_count > max_exams

    marks_qs = (
        ExamMark.objects.filter(student=student)
        .select_related(
            "learning_area",
            "generation",
            "generation__academic_year",
            "generation__academic_term",
        )
        .order_by(
            "-generation__created_at",
            "learning_area__display_order",
            "learning_area__name",
        )
    )

    if max_exams is not None:
        generation_ids = [
            row["generation_id"]
            for row in (
                ExamMark.objects.filter(student=student)
                .values("generation_id")
                .annotate(newest=Max("generation__created_at"))
                .order_by("-newest")[:max_exams]
            )
        ]
        if not generation_ids:
            return {
                "exams": [],
                "academic_class": academic_class_for_student(student, level=level),
                "level": level,
                "exams_truncated": exams_truncated,
                "total_exam_count": total_exam_count,
                "results_exam_limit": max_exams,
            }
        marks_qs = marks_qs.filter(generation_id__in=generation_ids)

    marks = list(marks_qs)
    exam_list = _build_exam_list(student, level=level, marks=marks, bands=bands)

    return {
        "exams": exam_list,
        "academic_class": academic_class_for_student(student, level=level),
        "level": level,
        "exams_truncated": exams_truncated,
        "total_exam_count": total_exam_count,
        "results_exam_limit": max_exams,
    }


def student_results_summary(student: Student) -> dict:
    """Dashboard-sized results snapshot: latest exam average + exam count only."""
    level = academic_level_for_student(student)
    bands = _bands_for_level(level)

    from django.db.models import Max

    generation_rows = list(
        ExamMark.objects.filter(student=student)
        .values("generation_id")
        .annotate(newest=Max("generation__created_at"))
        .order_by("-newest")
    )
    exam_count = len(generation_rows)
    if not generation_rows:
        return {
            "latest_average": None,
            "latest_grade": None,
            "latest_exam_name": None,
            "exam_count": 0,
        }

    latest_id = generation_rows[0]["generation_id"]
    marks = list(
        ExamMark.objects.filter(student=student, generation_id=latest_id)
        .select_related(
            "learning_area",
            "generation",
            "generation__academic_year",
            "generation__academic_term",
        )
        .order_by("learning_area__display_order", "learning_area__name")
    )
    exams = _build_exam_list(student, level=level, marks=marks, bands=bands)
    latest = exams[0] if exams else None
    return {
        "latest_average": latest["average_percent"] if latest else None,
        "latest_grade": (
            latest["average_grade"].code
            if latest and latest.get("average_grade")
            else None
        ),
        "latest_exam_name": latest["generation"].display_name if latest else None,
        "exam_count": exam_count,
    }


def results_comparison_table(exams: list[dict]) -> dict:
    """One subject-row × exam-column grid of percentages for side-by-side comparison."""
    if not exams:
        return {"exam_columns": [], "subject_rows": [], "average_row": []}

    # Oldest → newest so comparison reads left-to-right with the trend chart.
    columns = list(reversed(exams))
    exam_columns = [
        {
            "id": exam["generation"].pk,
            "name": exam["generation"].display_name,
            "average_percent": exam["average_percent"],
        }
        for exam in columns
    ]

    subjects: OrderedDict[int, dict] = OrderedDict()
    for exam in columns:
        for row in exam["rows"]:
            subject = row["subject"]
            subjects.setdefault(
                subject.pk,
                {
                    "id": subject.pk,
                    "name": subject.name,
                    "code": subject.code,
                    "order": getattr(subject, "display_order", 0) or 0,
                    "scores": {},
                },
            )
            subjects[subject.pk]["scores"][exam["generation"].pk] = row["percent"]

    subject_rows = []
    for subject in sorted(subjects.values(), key=lambda item: (item["order"], item["name"])):
        cells = [
            subject["scores"].get(column["id"]) for column in exam_columns
        ]
        subject_rows.append(
            {
                "name": subject["name"],
                "code": subject["code"],
                "percents": cells,
            }
        )

    average_row = [exam["average_percent"] for exam in columns]
    return {
        "exam_columns": exam_columns,
        "subject_rows": subject_rows,
        "average_row": average_row,
    }


def results_chart_payload(exams: list[dict], *, mode: str = "all") -> dict:
    """Build Chart.js-ready labels/datasets for exam averages or a single exam's subjects."""
    if mode == "all":
        chronological = list(reversed(exams))
        labels = [exam["generation"].display_name for exam in chronological]
        averages = [
            exam["average_percent"] if exam["average_percent"] is not None else None
            for exam in chronological
        ]
        return {
            "mode": "all",
            "type": "line",
            "labels": labels,
            "datasets": [
                {
                    "label": "Exam average %",
                    "data": averages,
                }
            ],
            "y_label": "Average %",
        }

    exam = exams[0] if exams else None
    if exam is None:
        return {
            "mode": "exam",
            "type": "bar",
            "labels": [],
            "datasets": [{"label": "Score %", "data": []}],
            "y_label": "Score %",
        }

    labels = [row["subject"].name for row in exam["rows"]]
    percents = [row["percent"] if row["percent"] is not None else None for row in exam["rows"]]
    return {
        "mode": "exam",
        "type": "bar",
        "labels": labels,
        "datasets": [
            {
                "label": "Score %",
                "data": percents,
            }
        ],
        "y_label": "Score %",
        "exam_name": exam["generation"].display_name,
    }


def student_timetable(student: Student):
    level = academic_level_for_student(student)
    academic_class = academic_class_for_student(student, level=level)
    if academic_class is None:
        return {
            "academic_class": None,
            "days": [],
            "day_labels": WEEKDAY_LABELS,
            "periods": [],
            "rows": [],
        }

    # Only the newest timetable generation for this class (admin regenerations accumulate).
    latest_generation_id = (
        GeneratedLearningLesson.objects.filter(academic_class=academic_class)
        .order_by("-generation_id")
        .values_list("generation_id", flat=True)
        .first()
    )
    lessons_qs = GeneratedLearningLesson.objects.filter(academic_class=academic_class)
    if latest_generation_id is not None:
        lessons_qs = lessons_qs.filter(generation_id=latest_generation_id)
    lessons = list(
        lessons_qs.select_related("learning_area", "teacher", "academic_class").order_by(
            "weekday", "start_time", "period_name"
        )
    )
    if not lessons:
        return {
            "academic_class": academic_class,
            "days": [],
            "day_labels": WEEKDAY_LABELS,
            "periods": [],
            "rows": [],
        }

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

    grid: dict[tuple, GeneratedLearningLesson] = {}
    for lesson in lessons:
        key = (lesson.weekday, lesson.period_name, lesson.start_time, lesson.end_time)
        grid[key] = lesson

    # Days as rows, periods as columns.
    rows = []
    for day in days:
        cells = []
        for period in periods:
            cells.append(
                grid.get((day, period["name"], period["start"], period["end"]))
            )
        rows.append(
            {
                "code": day,
                "label": WEEKDAY_LABELS.get(day, day),
                "cells": cells,
            }
        )

    return {
        "academic_class": academic_class,
        "days": days,
        "day_labels": WEEKDAY_LABELS,
        "periods": periods,
        "rows": rows,
    }


def student_conduct(student: Student, limit: int = 80):
    records = list(
        StudentConductRecord.objects.filter(student=student).order_by(
            "-incident_date", "-created_at"
        )[:limit]
    )
    good_count = sum(
        1
        for record in records
        if record.behaviour_type == StudentConductRecord.BehaviourType.GOOD
    )
    bad_count = sum(
        1
        for record in records
        if record.behaviour_type == StudentConductRecord.BehaviourType.BAD
    )
    return {
        "records": records,
        "total_count": len(records),
        "good_count": good_count,
        "bad_count": bad_count,
    }
