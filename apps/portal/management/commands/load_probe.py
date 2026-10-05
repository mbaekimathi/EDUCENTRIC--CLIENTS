"""Concurrent smoke probe for portal hot paths (login + heavy pages)."""

from __future__ import annotations

import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.core.management.base import BaseCommand, CommandError
from django.test import Client

from apps.portal import session as portal_session
from apps.portal.models import Student


PATHS = (
    "/dashboard/",
    "/attendance/",
    "/conduct/",
    "/results/",
    "/timetable/",
    "/academic-calendar/",
    "/finances/",
    "/e-learning/",
    "/profile/",
)


class Command(BaseCommand):
    help = (
        "Run concurrent portal requests (student session) and report OK rate and p95 latency."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--workers",
            type=int,
            default=10,
            help="Number of concurrent workers (default 10).",
        )
        parser.add_argument(
            "--student-id",
            type=int,
            default=0,
            help="Student primary key to impersonate (default: first eligible).",
        )
        parser.add_argument(
            "--role",
            choices=("student", "parent"),
            default="student",
            help="Portal role to simulate after login.",
        )

    def handle(self, *args, **options):
        workers = max(1, options["workers"])
        student = self._resolve_student(options["student_id"])
        role = options["role"]

        durations: list[float] = []
        errors = 0
        total = 0

        def _seed_session(store, *, as_parent: bool) -> None:
            store.flush()
            if as_parent and student.parent_guardian_id:
                store[portal_session.SESSION_ROLE] = portal_session.ROLE_PARENT
                store[portal_session.SESSION_PARENT_ID] = student.parent_guardian_id
                store[portal_session.SESSION_STUDENT_ID] = student.pk
            else:
                store[portal_session.SESSION_ROLE] = portal_session.ROLE_STUDENT
                store[portal_session.SESSION_STUDENT_ID] = student.pk
            store.save()

        def run_probe(worker_index: int) -> tuple[float, bool]:
            client = Client()
            _seed_session(
                client.session,
                as_parent=(
                    role == portal_session.ROLE_PARENT and bool(student.parent_guardian_id)
                ),
            )

            started = time.perf_counter()
            ok = True
            for path in PATHS:
                response = client.get(path)
                if response.status_code >= 400:
                    ok = False
                    break
            elapsed_ms = (time.perf_counter() - started) * 1000
            return elapsed_ms, ok

        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(run_probe, i) for i in range(workers)]
            for future in as_completed(futures):
                total += 1
                try:
                    ms, ok = future.result()
                except Exception as exc:
                    errors += 1
                    self.stderr.write(f"worker error: {exc!r}")
                    continue
                durations.append(ms)
                if not ok:
                    errors += 1

        wall = (time.perf_counter() - started) * 1000
        ok_count = total - errors
        ok_pct = (ok_count * 100 / total) if total else 0
        p95 = statistics.quantiles(durations, n=20)[18] if len(durations) >= 2 else (
            durations[0] if durations else 0
        )

        self.stdout.write(
            f"Student {student.pk} ({student.display_name}) · role={role} · workers={workers}"
        )
        self.stdout.write(f"Paths: {', '.join(PATHS)}")
        self.stdout.write(f"OK: {ok_count}/{total} ({ok_pct:.1f}%)")
        self.stdout.write(f"p95 latency: {p95:.0f} ms (per worker full path set)")
        self.stdout.write(f"Wall time: {wall:.0f} ms")
        if errors:
            raise CommandError(f"{errors} worker(s) reported failures or 5xx.")

    def _resolve_student(self, student_id: int) -> Student:
        if student_id:
            student = (
                Student.objects.select_related("parent_guardian")
                .filter(pk=student_id, is_suspended=False)
                .first()
            )
            if student is None:
                raise CommandError(f"No eligible student with id={student_id}.")
            return student

        student = (
            Student.objects.select_related("parent_guardian")
            .filter(is_suspended=False)
            .order_by("pk")
            .first()
        )
        if student is None:
            raise CommandError("No eligible students in the database.")
        return student
