"""Dashboard analytics and school-activity notifications for the portal home."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.db.models import Max, Min, Prefetch, Q

from . import elearning as elearning_service
from . import student_records
from .activity_models import SchoolActivity, SchoolActivityDay
from .curriculum_models import AcademicYear
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
    """Load current + upcoming dashboard notifications from published school activities."""
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


def _activity_grade_labels(activity: SchoolActivity) -> list[str]:
    labels: list[str] = []
    for link in activity.grade_links.all():
        level = getattr(link, "academiclevel", None)
        name = getattr(level, "name", None) if level is not None else None
        if name:
            labels.append(str(name))
    return labels


def academic_calendar_timeline(
    student: Student | None = None,
    today: date | None = None,
) -> dict:
    """School activities calendar for the dedicated Academic calendar page."""
    today = today or date.today()
    year = _current_academic_year_cached(today)

    day_qs = SchoolActivityDay.objects.order_by("activity_date", "id")
    activity_qs = (
        SchoolActivity.objects.filter(status="PUBLISHED")
        .prefetch_related(
            Prefetch("days", queryset=day_qs),
            "grade_links__academiclevel",
        )
        .annotate(
            first_day=Min("days__activity_date"),
            last_day=Max("days__activity_date"),
        )
        .filter(first_day__isnull=False)
    )

    if year is not None:
        activity_qs = activity_qs.filter(
            first_day__lte=year.end_date,
            last_day__gte=year.start_date,
        )

    events: list[dict] = []
    for activity in activity_qs.order_by("first_day", "title"):
        days = list(activity.days.all())
        if not days:
            continue
        start = days[0].activity_date
        end = days[-1].activity_date
        description = (activity.description or "").strip()
        if not description and days[0].day_description:
            description = days[0].day_description
        day_notes = [
            {
                "date": d.activity_date,
                "label": _fmt_day(d.activity_date),
                "note": d.day_description,
            }
            for d in days
            if d.day_description
        ]
        grades = _activity_grade_labels(activity)
        status = _event_status(start, end, today)
        days_away = _days_until(start, today) if status == "upcoming" else 0
        if status == "current":
            when_label = "Happening now"
        elif status == "upcoming":
            when_label = (
                "Tomorrow"
                if days_away == 1
                else f"In {days_away} days"
                if days_away > 0
                else "Upcoming"
            )
        else:
            when_label = "Finished"
        events.append(
            {
                "kind": "activity",
                "title": activity.title,
                "description": (
                    description.splitlines()[0][:200] if description else ""
                ),
                "start": start,
                "end": end,
                "status": status,
                "date_label": _fmt_range(start, end),
                "iso_start": start.isoformat(),
                "iso_end": end.isoformat(),
                "duration_days": (end - start).days + 1,
                "when_label": when_label,
                "day_notes": day_notes,
                "grades": grades,
                "grades_label": ", ".join(grades) if grades else "Whole school",
            }
        )

    current_events = [e for e in events if e["status"] == "current"]
    upcoming_events = sorted(
        [e for e in events if e["status"] == "upcoming"],
        key=lambda item: (item["start"], item["title"]),
    )
    past_events = sorted(
        [e for e in events if e["status"] == "past"],
        key=lambda item: (item["start"], item["title"]),
        reverse=True,
    )

    max_upcoming = getattr(settings, "PORTAL_CALENDAR_MAX_UPCOMING", 50)
    max_past = getattr(settings, "PORTAL_CALENDAR_MAX_PAST", 30)
    calendar_truncated = False
    if len(upcoming_events) > max_upcoming:
        upcoming_events = upcoming_events[:max_upcoming]
        calendar_truncated = True
    if len(past_events) > max_past:
        past_events = past_events[:max_past]
        calendar_truncated = True

    return {
        "academic_year": year,
        "today": today,
        "events": events,
        "current_events": current_events,
        "upcoming_events": upcoming_events,
        "past_events": past_events,
        "calendar_truncated": calendar_truncated,
        "calendar_upcoming_limit": max_upcoming,
        "calendar_past_limit": max_past,
        "counts": {
            "total": len(events),
            "current": len(current_events),
            "upcoming": len(upcoming_events),
            "past": len(past_events),
        },
        "has_activities": bool(events),
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
