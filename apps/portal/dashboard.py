"""Dashboard analytics and academic-calendar notifications for the portal home."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Max, Min, Prefetch, Q

from . import elearning as elearning_service
from . import student_records
from .activity_models import SchoolActivity, SchoolActivityDay
from .curriculum_models import AcademicTerm, AcademicYear, GeneratedExamTimetable
from .finance_models import student_finance_balance
from .models import Student


def _fmt_day(value: date) -> str:
    return value.strftime("%d %b %Y").lstrip("0")


def _fmt_range(start: date | None, end: date | None) -> str:
    if start and end:
        if start == end:
            return _fmt_day(start)
        return f"{_fmt_day(start)} - {_fmt_day(end)}"
    if start:
        return _fmt_day(start)
    if end:
        return _fmt_day(end)
    return ""


def _days_until(target: date, today: date) -> int:
    return (target - today).days


def _current_academic_year(today: date) -> AcademicYear | None:
    year = AcademicYear.objects.filter(is_current=True).order_by("-start_date").first()
    if year is not None:
        return year
    return (
        AcademicYear.objects.filter(start_date__lte=today, end_date__gte=today)
        .order_by("-start_date")
        .first()
    )


def _activity_applies_to_student(
    activity: SchoolActivity,
    student: Student | None,
    level=None,
) -> bool:
    """Respect grade targeting from employees_schoolactivity_grades when present."""
    grade_ids = [link.academiclevel_id for link in activity.grade_links.all()]
    if not grade_ids:
        return True
    if student is None:
        return True
    if level is None:
        level = student_records.academic_level_for_student(student)
    if level is None:
        return False
    return level.pk in grade_ids


def _current_academic_year_cached(today: date) -> AcademicYear | None:
    cache_key = f"portal:current_academic_year:{today.isoformat()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached or None
    year = _current_academic_year(today)
    cache.set(cache_key, year if year is not None else False, 120)
    return year


def academic_calendar_notifications(
    student: Student | None = None,
    today: date | None = None,
    upcoming_days: int = 90,
) -> dict:
    """Load current + upcoming notifications from DB terms, exams, and school activities."""
    today = today or date.today()
    horizon = today + timedelta(days=upcoming_days)
    student_level = (
        student_records.academic_level_for_student(student) if student is not None else None
    )

    current: list[dict] = []
    upcoming: list[dict] = []
    seen: set[tuple] = set()

    def push(bucket: list[dict], item: dict):
        key = (item.get("kind"), item.get("title"), item.get("start"), item.get("end"), item.get("detail"))
        if key in seen:
            return
        seen.add(key)
        bucket.append(item)

    year = _current_academic_year_cached(today)
    terms: list[AcademicTerm] = []
    if year is not None:
        terms_key = f"portal:year_terms:{year.pk}"
        terms = cache.get(terms_key)
        if terms is None:
            terms = list(
                AcademicTerm.objects.filter(academic_year=year)
                .select_related("academic_year")
                .order_by("order", "start_date")
            )
            cache.set(terms_key, terms, 120)
        if year.start_date <= today <= year.end_date:
            push(
                current,
                {
                    "kind": "year",
                    "title": f"Academic year {year.name}",
                    "detail": _fmt_range(year.start_date, year.end_date),
                    "start": year.start_date,
                    "end": year.end_date,
                    "badge": "Now",
                },
            )

    date_matched_terms = [t for t in terms if t.start_date <= today <= t.end_date]
    for term in terms:
        in_term = term in date_matched_terms
        treat_as_current = in_term or (
            term.is_current and not date_matched_terms
        )
        if treat_as_current:
            days_left = max(0, (term.end_date - today).days)
            push(
                current,
                {
                    "kind": "term",
                    "title": f"{term.name} in progress",
                    "detail": (
                        f"{_fmt_range(term.start_date, term.end_date)}"
                        + (f" · {days_left} day{'s' if days_left != 1 else ''} left" if days_left else "")
                    ),
                    "start": term.start_date,
                    "end": term.end_date,
                    "badge": "Current",
                },
            )
            if today < term.end_date <= horizon:
                push(
                    upcoming,
                    {
                        "kind": "term_end",
                        "title": f"{term.name} closes",
                        "detail": (
                            f"{_fmt_day(term.end_date)}"
                            f" · in {_days_until(term.end_date, today)} days"
                        ),
                        "start": term.end_date,
                        "end": term.end_date,
                        "badge": "Closing",
                    },
                )

        if today < term.start_date <= horizon:
            push(
                upcoming,
                {
                    "kind": "term_start",
                    "title": f"{term.name} opens",
                    "detail": (
                        f"{_fmt_day(term.start_date)}"
                        f" · in {_days_until(term.start_date, today)} days"
                    ),
                    "start": term.start_date,
                    "end": term.end_date,
                    "badge": "Opening",
                },
            )

    # Exam windows stored on generated exam timetables
    exam_filter = Q(start_date__isnull=False) & (
        Q(end_date__gte=today, start_date__lte=horizon)
        | Q(end_date__isnull=True, start_date__gte=today, start_date__lte=horizon)
    )
    if year is not None:
        exam_filter &= Q(academic_year=year) | Q(academic_year__isnull=True)

    for exam in (
        GeneratedExamTimetable.objects.filter(exam_filter)
        .select_related("academic_year", "academic_term")
        .order_by("start_date", "-created_at")[:12]
    ):
        start = exam.start_date
        end = exam.end_date or exam.start_date
        if start is None:
            continue
        title = exam.display_name
        if start <= today <= end:
            push(
                current,
                {
                    "kind": "exam",
                    "title": title,
                    "detail": _fmt_range(start, end),
                    "start": start,
                    "end": end,
                    "badge": "Exams",
                },
            )
        elif today < start <= horizon:
            push(
                upcoming,
                {
                    "kind": "exam",
                    "title": title,
                    "detail": (
                        f"{_fmt_range(start, end)}"
                        f" · in {_days_until(start, today)} days"
                    ),
                    "start": start,
                    "end": end,
                    "badge": "Exams",
                },
            )

    # School calendar activities published in ADMINISTRATION
    day_qs = SchoolActivityDay.objects.order_by("activity_date", "id")
    activities = (
        SchoolActivity.objects.filter(status="PUBLISHED")
        .prefetch_related(
            Prefetch("days", queryset=day_qs),
            "grade_links",
        )
        .annotate(
            first_day=Min("days__activity_date"),
            last_day=Max("days__activity_date"),
        )
        .filter(
            Q(first_day__lte=horizon, last_day__gte=today)
            | Q(first_day__gte=today, first_day__lte=horizon)
        )
        .order_by("first_day", "title")
    )

    for activity in activities:
        if not _activity_applies_to_student(activity, student, level=student_level):
            continue
        days = list(activity.days.all())
        if not days:
            continue
        start = days[0].activity_date
        end = days[-1].activity_date
        today_days = [d for d in days if d.activity_date == today]
        future_days = [d for d in days if d.activity_date > today]

        if today_days or (start <= today <= end):
            detail_parts = [_fmt_range(start, end)]
            if today_days and today_days[0].day_description:
                detail_parts.append(today_days[0].day_description)
            elif activity.description:
                detail_parts.append(activity.description.strip().splitlines()[0][:120])
            push(
                current,
                {
                    "kind": "activity",
                    "title": activity.title,
                    "detail": " · ".join(p for p in detail_parts if p),
                    "start": start,
                    "end": end,
                    "badge": "Today" if today_days else "Ongoing",
                },
            )

        if future_days:
            next_day = future_days[0]
            detail_parts = [
                _fmt_day(next_day.activity_date),
                f"in {_days_until(next_day.activity_date, today)} days",
            ]
            if next_day.day_description:
                detail_parts.append(next_day.day_description)
            push(
                upcoming,
                {
                    "kind": "activity",
                    "title": activity.title,
                    "detail": " · ".join(detail_parts),
                    "start": next_day.activity_date,
                    "end": end,
                    "badge": "Activity",
                },
            )

    upcoming.sort(key=lambda item: (item.get("start") or today, item.get("title") or ""))
    return {
        "academic_year": year,
        "current_events": current,
        "upcoming_events": upcoming[:10],
        "today": today,
    }


def _event_status(start: date | None, end: date | None, today: date) -> str:
    if start is None:
        return "upcoming"
    end = end or start
    if end < today:
        return "past"
    if start <= today <= end:
        return "current"
    return "upcoming"


def _month_key(value: date) -> str:
    return value.strftime("%Y-%m")


def _month_label(value: date) -> str:
    return value.strftime("%B %Y")


def academic_calendar_timeline(
    student: Student | None = None,
    today: date | None = None,
) -> dict:
    """Full chronological calendar for the dedicated Academic calendar page."""
    today = today or date.today()
    year = _current_academic_year_cached(today)
    student_level = (
        student_records.academic_level_for_student(student) if student is not None else None
    )
    events: list[dict] = []
    seen: set[tuple] = set()

    def add(item: dict):
        key = (item.get("kind"), item.get("title"), item.get("start"), item.get("end"))
        if key in seen:
            return
        seen.add(key)
        start = item.get("start")
        end = item.get("end") or start
        item["end"] = end
        item["status"] = _event_status(start, end, today)
        item["date_label"] = _fmt_range(start, end)
        item["day_num"] = start.day if start else ""
        item["weekday"] = start.strftime("%a") if start else ""
        item["month_short"] = start.strftime("%b") if start else ""
        item["iso_start"] = start.isoformat() if start else ""
        item["iso_end"] = end.isoformat() if end else ""
        item["duration_days"] = ((end - start).days + 1) if start and end else 1
        events.append(item)

    if year is not None:
        add(
            {
                "kind": "year",
                "title": f"Academic year {year.name}",
                "description": "Full school year",
                "start": year.start_date,
                "end": year.end_date,
                "badge": "Year",
            }
        )
        terms_key = f"portal:year_terms:{year.pk}"
        terms = cache.get(terms_key)
        if terms is None:
            terms = list(
                AcademicTerm.objects.filter(academic_year=year)
                .select_related("academic_year")
                .order_by("order", "start_date")
            )
            cache.set(terms_key, terms, 120)
        for term in terms:
            add(
                {
                    "kind": "term",
                    "title": term.name,
                    "description": "Academic term",
                    "start": term.start_date,
                    "end": term.end_date,
                    "badge": "Term",
                }
            )

    exam_filter = Q(start_date__isnull=False)
    if year is not None:
        exam_filter &= Q(academic_year=year) | Q(academic_year__isnull=True)
        exam_filter &= Q(start_date__lte=year.end_date, end_date__gte=year.start_date) | Q(
            end_date__isnull=True,
            start_date__gte=year.start_date,
            start_date__lte=year.end_date,
        )

    for exam in (
        GeneratedExamTimetable.objects.filter(exam_filter)
        .select_related("academic_year", "academic_term")
        .order_by("start_date", "-created_at")
    ):
        start = exam.start_date
        if start is None:
            continue
        end = exam.end_date or start
        add(
            {
                "kind": "exam",
                "title": exam.display_name,
                "description": "Examination window",
                "start": start,
                "end": end,
                "badge": "Exams",
            }
        )

    day_qs = SchoolActivityDay.objects.order_by("activity_date", "id")
    activity_qs = SchoolActivity.objects.filter(status="PUBLISHED").prefetch_related(
        Prefetch("days", queryset=day_qs),
        "grade_links",
    )
    if year is not None:
        activity_qs = activity_qs.annotate(
            first_day=Min("days__activity_date"),
            last_day=Max("days__activity_date"),
        ).filter(
            first_day__isnull=False,
            first_day__lte=year.end_date,
            last_day__gte=year.start_date,
        )
    else:
        activity_qs = activity_qs.annotate(
            first_day=Min("days__activity_date"),
            last_day=Max("days__activity_date"),
        ).filter(first_day__isnull=False)

    for activity in activity_qs.order_by("first_day", "title"):
        if not _activity_applies_to_student(activity, student, level=student_level):
            continue
        days = list(activity.days.all())
        if not days:
            continue
        start = days[0].activity_date
        end = days[-1].activity_date
        description = (activity.description or "").strip()
        if not description and days[0].day_description:
            description = days[0].day_description
        day_notes = [
            {"date": d.activity_date, "label": _fmt_day(d.activity_date), "note": d.day_description}
            for d in days
            if d.day_description
        ]
        add(
            {
                "kind": "activity",
                "title": activity.title,
                "description": description.splitlines()[0][:160] if description else "School activity",
                "start": start,
                "end": end,
                "badge": "Activity",
                "day_notes": day_notes,
            }
        )

    events.sort(key=lambda item: (item.get("start") or today, item.get("end") or today, item.get("title") or ""))

    focus_set = False
    for event in events:
        if not focus_set and event["status"] in ("current", "upcoming"):
            event["is_focus"] = True
            focus_set = True
        else:
            event["is_focus"] = False

    months: list[dict] = []
    month_index: dict[str, dict] = {}
    for event in events:
        start = event.get("start")
        if start is None:
            continue
        key = _month_key(start)
        if key not in month_index:
            group = {
                "key": key,
                "label": _month_label(start),
                "events": [],
            }
            month_index[key] = group
            months.append(group)
        month_index[key]["events"].append(event)

    counts = {
        "total": len(events),
        "current": sum(1 for e in events if e["status"] == "current"),
        "upcoming": sum(1 for e in events if e["status"] == "upcoming"),
        "past": sum(1 for e in events if e["status"] == "past"),
    }

    return {
        "academic_year": year,
        "today": today,
        "events": events,
        "months": months,
        "counts": counts,
        "has_focus": focus_set,
    }


def student_dashboard(student: Student) -> dict:
    """Slim KPI dashboard — avoid full results / finance / e-learning payloads."""
    attendance = student_records.student_attendance(
        student, limit=40, include_class=False
    )
    results = student_records.student_results_summary(student)
    finance = student_finance_balance(student.pk)
    elearning_count = elearning_service.student_elearning_count(student)
    calendar = academic_calendar_notifications(student=student)

    balance = finance["balance"]

    analytics = {
        "attendance_rate": attendance["attendance_rate"],
        "days_recorded": attendance["days_recorded"],
        "present_slots": attendance["present_slots"],
        "total_slots": attendance["total_slots"],
        "latest_average": results["latest_average"],
        "latest_grade": results["latest_grade"],
        "latest_exam_name": results["latest_exam_name"],
        "exam_count": results["exam_count"],
        "fee_balance": balance,
        "fee_balance_display": f"{balance:,.2f}",
        "fees_clear": balance <= Decimal("0.00"),
        "elearning_count": elearning_count,
    }

    return {
        "analytics": analytics,
        **calendar,
    }
