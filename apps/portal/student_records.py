"""Helpers to load attendance, exam results, and timetable for a portal student."""

from __future__ import annotations

import re
from collections import OrderedDict

from .curriculum_models import (
    AcademicClass,
    AcademicLevel,
    ClassAttendanceRecord,
    ExamMark,
    ExamSubjectSetting,
    GeneratedExamTimetable,
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


def _student_level_choice(level: AcademicLevel) -> str:
    name = (level.name or "").strip()
    for value, label in Student.AcademicLevel.choices:
        if label.casefold() == name.casefold():
            return value
        if value.replace("_", " ").casefold() == name.casefold():
            return value
    return ""


def academic_level_for_student(student: Student) -> AcademicLevel | None:
    for level in AcademicLevel.objects.filter(status="ACTIVE"):
        if _student_level_choice(level) == student.academic_level:
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


def academic_class_for_student(student: Student) -> AcademicClass | None:
    level = academic_level_for_student(student)
    if level is None:
        return None
    classes = list(
        AcademicClass.objects.filter(academic_level=level, status="ACTIVE")
        .select_related("academic_level")
        .order_by("order", "name")
    )
    if not classes:
        return None

    raw = (student.class_group or "").strip()
    if raw:
        for academic_class in classes:
            values = _class_group_values(academic_class)
            if any(raw.casefold() == value.casefold() for value in values):
                return academic_class

    if len(classes) == 1:
        return classes[0]
    return None


def _grade_for_percent(percent: int | None, level: AcademicLevel | None) -> GradeBand | None:
    if percent is None:
        return None
    bands = GradeBand.objects.all()
    if level is not None:
        level_bands = list(bands.filter(academic_level=level))
        if level_bands:
            bands = level_bands
        else:
            bands = list(bands.filter(academic_level__isnull=True))
    else:
        bands = list(bands.filter(academic_level__isnull=True))
    for band in bands:
        if band.start_percent <= percent <= band.end_percent:
            return band
    return None


def student_attendance(student: Student, limit: int = 60):
    records = list(
        ClassAttendanceRecord.objects.filter(student=student)
        .select_related("session", "session__academic_class")
        .order_by("-session__attendance_date", "-updated_at")[:limit]
    )
    total_slots = 0
    present_slots = 0
    for record in records:
        for flag in (record.morning, record.afternoon, record.evening):
            total_slots += 1
            if flag:
                present_slots += 1
    rate = round((present_slots * 100) / total_slots) if total_slots else None
    return {
        "records": records,
        "days_recorded": len(records),
        "present_slots": present_slots,
        "total_slots": total_slots,
        "attendance_rate": rate,
        "academic_class": academic_class_for_student(student),
    }


def student_results(student: Student):
    level = academic_level_for_student(student)
    out_of_by_area: dict[int, int] = {}
    if level is not None:
        for setting in ExamSubjectSetting.objects.filter(academic_level=level).select_related(
            "learning_area"
        ):
            out_of_by_area[setting.learning_area_id] = setting.out_of_marks

    marks = list(
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
        percent = round((mark.marks * 100) / out_of) if out_of else None
        grade = _grade_for_percent(percent, level)
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
                "average_grade": _grade_for_percent(avg, level),
            }
        )

    return {
        "exams": exam_list,
        "academic_class": academic_class_for_student(student),
        "level": level,
    }


def student_timetable(student: Student):
    academic_class = academic_class_for_student(student)
    if academic_class is None:
        return {
            "academic_class": None,
            "days": [],
            "day_labels": WEEKDAY_LABELS,
            "periods": [],
            "rows": [],
        }

    lessons = list(
        GeneratedLearningLesson.objects.filter(academic_class=academic_class)
        .select_related("learning_area", "teacher", "academic_class")
        .order_by("weekday", "start_time", "period_name")
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
