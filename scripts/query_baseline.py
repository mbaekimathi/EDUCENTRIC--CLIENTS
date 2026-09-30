"""Measure ORM query counts for hot portal loaders (baseline / after fixes)."""
from __future__ import annotations

import os
import sys
import time

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from django.db import connection, reset_queries
from django.conf import settings

settings.DEBUG = True  # enable query logging for this process only

from apps.portal.models import Student
from apps.portal import student_records, dashboard as portal_dashboard
from apps.portal.finance_models import student_finance_summary
from apps.portal import elearning as elearning_service


def measure(label, fn):
    reset_queries()
    started = time.perf_counter()
    result = fn()
    ms = (time.perf_counter() - started) * 1000
    n = len(connection.queries)
    print(f"{label:<22} queries={n:>4}  {ms:7.1f}ms")
    return result


def main():
    s = Student.objects.select_related("parent_guardian").filter(pk=2).first()
    if s is None:
        print("No student pk=2")
        return 1
    print(f"Student: {s.pk} {s.display_name}")
    measure("attendance", lambda: student_records.student_attendance(s))
    measure("results", lambda: student_records.student_results(s))
    measure("timetable", lambda: student_records.student_timetable(s))
    measure("conduct", lambda: student_records.student_conduct(s))
    measure("finance", lambda: student_finance_summary(s.pk))
    measure("elearning", lambda: elearning_service.student_elearning_subjects(s))
    measure("calendar_timeline", lambda: portal_dashboard.academic_calendar_timeline(student=s))
    measure("calendar_notify", lambda: portal_dashboard.academic_calendar_notifications(student=s))
    measure("dashboard", lambda: portal_dashboard.student_dashboard(s))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
