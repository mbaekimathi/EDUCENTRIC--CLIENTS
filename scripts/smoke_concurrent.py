"""
Concurrent portal smoke test — measures page latency under multi-client load.

Usage:
  python scripts/smoke_concurrent.py [--base http://127.0.0.1:8000] [--clients 8] [--rounds 2]
"""

from __future__ import annotations

import argparse
import re
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import HTTPCookieProcessor, Request, build_opener

PAGES = [
    ("dashboard", "/dashboard/"),
    ("attendance", "/attendance/"),
    ("conduct", "/conduct/"),
    ("results", "/results/"),
    ("timetable", "/timetable/"),
    ("academic_calendar", "/academic-calendar/"),
    ("finances", "/finances/"),
    ("elearning", "/e-learning/"),
    ("profile", "/profile/"),
]


@dataclass
class Sample:
    page: str
    status: int
    ms: float
    bytes: int
    error: str = ""


@dataclass
class ClientResult:
    student_id: int
    samples: list[Sample] = field(default_factory=list)


def _opener():
    return build_opener(HTTPCookieProcessor(CookieJar()))


def _fetch(
    opener,
    url: str,
    data: bytes | None = None,
    method: str | None = None,
    referer: str | None = None,
) -> tuple[int, bytes, float]:
    headers = {
        "User-Agent": "EducentricSmoke/1.0",
        "Accept": "text/html,application/json",
    }
    if referer:
        headers["Referer"] = referer
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = Request(url, data=data, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with opener.open(req, timeout=60) as resp:
            body = resp.read()
            status = getattr(resp, "status", 200) or 200
            return status, body, (time.perf_counter() - started) * 1000
    except HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return exc.code, body, (time.perf_counter() - started) * 1000


def _csrf(html: bytes) -> str:
    text = html.decode("utf-8", errors="ignore")
    match = re.search(r'name=["\']csrfmiddlewaretoken["\']\s+value=["\']([^"\']+)', text)
    if not match:
        match = re.search(r'csrfmiddlewaretoken["\']?\s*[:=]\s*["\']([^"\']+)', text)
    if not match:
        raise RuntimeError("CSRF token not found on login page")
    return match.group(1)


def login_client(base: str, student_id: int, role: str = "student") -> object:
    opener = _opener()
    status, body, _ = _fetch(opener, urljoin(base, "/"))
    if status >= 400:
        raise RuntimeError(f"login page HTTP {status}")
    token = _csrf(body)
    payload = urlencode(
        {
            "csrfmiddlewaretoken": token,
            "role": role,
            "student_id": str(student_id),
        }
    ).encode()
    status, body, _ = _fetch(
        opener,
        urljoin(base, "/"),
        data=payload,
        referer=urljoin(base, "/"),
    )
    # Expect redirect to dashboard (urllib follows redirects by default).
    if status >= 400:
        raise RuntimeError(f"login POST HTTP {status}: {body[:200]!r}")
    return opener


def run_client(base: str, student_id: int, rounds: int) -> ClientResult:
    result = ClientResult(student_id=student_id)
    try:
        opener = login_client(base, student_id)
    except (URLError, RuntimeError, OSError) as exc:
        result.samples.append(
            Sample(page="login", status=0, ms=0, bytes=0, error=str(exc))
        )
        return result

    for _ in range(rounds):
        for name, path in PAGES:
            try:
                status, body, ms = _fetch(opener, urljoin(base, path))
                result.samples.append(
                    Sample(page=name, status=status, ms=ms, bytes=len(body))
                )
            except (URLError, OSError) as exc:
                result.samples.append(
                    Sample(page=name, status=0, ms=0, bytes=0, error=str(exc))
                )
    return result


def summarize(results: list[ClientResult]) -> int:
    by_page: dict[str, list[Sample]] = {}
    errors = 0
    for client in results:
        for sample in client.samples:
            by_page.setdefault(sample.page, []).append(sample)
            if sample.error or sample.status >= 400 or sample.status == 0:
                errors += 1

    print("\n=== Concurrent smoke summary ===")
    print(f"Clients: {len(results)}  |  Failed samples: {errors}")
    print(f"{'page':<20} {'n':>4} {'p50':>8} {'p95':>8} {'max':>8} {'avg':>8} {'err':>4}")
    slowest = []
    for name, _ in [("login", None), *PAGES]:
        samples = by_page.get(name, [])
        if not samples:
            continue
        ok = [s.ms for s in samples if not s.error and 200 <= s.status < 400]
        err_n = len(samples) - len(ok)
        if ok:
            ok_sorted = sorted(ok)
            p50 = ok_sorted[len(ok_sorted) // 2]
            p95 = ok_sorted[max(0, int(len(ok_sorted) * 0.95) - 1)]
            mx = max(ok)
            avg = statistics.fmean(ok)
            print(
                f"{name:<20} {len(ok):>4} {p50:7.0f}ms {p95:7.0f}ms {mx:7.0f}ms {avg:7.0f}ms {err_n:>4}"
            )
            slowest.append((name, p95, avg, mx))
        else:
            print(f"{name:<20} {0:>4} {'—':>8} {'—':>8} {'—':>8} {'—':>8} {err_n:>4}")

    if slowest:
        print("\nSlowest by p95:")
        for name, p95, avg, mx in sorted(slowest, key=lambda row: row[1], reverse=True)[:5]:
            print(f"  {name}: p95={p95:.0f}ms avg={avg:.0f}ms max={mx:.0f}ms")
    return 1 if errors else 0


def discover_students(base: str, limit: int) -> list[int]:
    """Pull student IDs from the search API (unauthenticated)."""
    opener = _opener()
    status, body, _ = _fetch(opener, urljoin(base, "/api/students/search/?q="))
    if status != 200:
        raise RuntimeError(f"student search failed: HTTP {status}")
    import json

    data = json.loads(body.decode("utf-8"))
    ids = [int(row["id"]) for row in data.get("results", [])]
    if len(ids) < limit:
        # Fall back to sequential ids from first known batch + shell isn't available here.
        # Search with common letters to widen pool.
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            status, body, _ = _fetch(
                opener, urljoin(base, f"/api/students/search/?q={letter}")
            )
            if status != 200:
                continue
            for row in json.loads(body.decode("utf-8")).get("results", []):
                sid = int(row["id"])
                if sid not in ids:
                    ids.append(sid)
            if len(ids) >= limit:
                break
    return ids[:limit]


def main() -> int:
    parser = argparse.ArgumentParser(description="Concurrent portal smoke test")
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--clients", type=int, default=8)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument(
        "--students",
        default="",
        help="Comma-separated student IDs (optional; auto-discover otherwise)",
    )
    args = parser.parse_args()

    if args.students.strip():
        student_ids = [int(x) for x in args.students.split(",") if x.strip()]
    else:
        student_ids = discover_students(args.base, args.clients)

    if len(student_ids) < args.clients:
        print(
            f"Warning: only {len(student_ids)} students available for {args.clients} clients",
            file=sys.stderr,
        )
    student_ids = (student_ids * ((args.clients // max(len(student_ids), 1)) + 1))[
        : args.clients
    ]

    print(
        f"Smoke: {args.clients} clients × {args.rounds} rounds × {len(PAGES)} pages"
        f" against {args.base}"
    )
    print(f"Students: {student_ids}")

    wall_start = time.perf_counter()
    results: list[ClientResult] = []
    with ThreadPoolExecutor(max_workers=args.clients) as pool:
        futures = [
            pool.submit(run_client, args.base, sid, args.rounds) for sid in student_ids
        ]
        for fut in as_completed(futures):
            results.append(fut.result())
    wall_ms = (time.perf_counter() - wall_start) * 1000
    print(f"Wall clock: {wall_ms:.0f}ms")
    return summarize(results)


if __name__ == "__main__":
    raise SystemExit(main())
