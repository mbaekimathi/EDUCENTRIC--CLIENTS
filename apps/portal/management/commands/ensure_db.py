"""Apply migrations and create Django-owned tables when missing (idempotent)."""

from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = (
        "Run migrations with --run-syncdb so Django session/cache tables exist. "
        "Does not alter shared admissions/employee tables (managed=False). "
        "Run after ADMINISTRATION and ACCOUNTS on a shared database."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-syncdb",
            action="store_true",
            help="Skip run-syncdb (only apply migration files).",
        )

    def handle(self, *args, **options):
        verbosity = options.get("verbosity", 1)
        run_syncdb = not options["no_syncdb"]

        self.stdout.write("Checking database connection…")
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")

        self.stdout.write("Applying migrations (creates tables if none exist)…")
        migrate_kwargs = {"interactive": False, "verbosity": verbosity}
        if run_syncdb:
            migrate_kwargs["run_syncdb"] = True
        call_command("migrate", **migrate_kwargs)
        self.stdout.write(self.style.SUCCESS("CLIENTS database tables are up to date."))
