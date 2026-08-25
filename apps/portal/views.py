from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import session as portal_session
from . import student_records
from . import elearning as elearning_service
from .finance_models import student_finance_summary
from .models import Student


def _portal_student_or_redirect(request):
    student = request.portal_student
    if student is None:
        portal_session.clear_portal_session(request)
        return None, redirect(settings.PORTAL_LOGIN_URL)
    return student, None


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def _login_allowed(request):
    """Simple cache-backed throttle to blunt credential stuffing / abuse."""
    key = f"portal_login_rl:{_client_ip(request)}"
    hits = cache.get(key, 0)
    limit = getattr(settings, "PORTAL_LOGIN_RATE_LIMIT", 30)
    window = getattr(settings, "PORTAL_LOGIN_RATE_WINDOW", 300)
    if hits >= limit:
        return False
    cache.set(key, hits + 1, window)
    return True


def _eligible_students():
    return (
        Student.objects.select_related("parent_guardian")
        .filter(is_suspended=False)
        .order_by("last_name", "first_name")
    )


@portal_session.redirect_if_authenticated
@require_http_methods(["GET", "POST"])
def login_view(request):
    role = (request.POST.get("role") or request.GET.get("role") or "student").lower()
    if role not in (portal_session.ROLE_STUDENT, portal_session.ROLE_PARENT):
        role = portal_session.ROLE_STUDENT

    error = None

    if request.method == "POST":
        if not _login_allowed(request):
            error = "Too many login attempts. Please wait a few minutes and try again."
        else:
            student_id = request.POST.get("student_id")
            if not student_id:
                error = "Select a student to continue."
            else:
                student = (
                    _eligible_students()
                    .filter(pk=student_id)
                    .first()
                )
                if student is None:
                    error = "That student is not available for portal access."
                elif role == portal_session.ROLE_STUDENT:
                    portal_session.login_as_student(request, student)
                    messages.success(
                        request,
                        f"Welcome, {student.display_name}. You are signed in as a student.",
                    )
                    return redirect(settings.PORTAL_LOGIN_REDIRECT_URL)
                else:
                    parent = student.parent_guardian
                    if parent is None:
                        error = "No parent/guardian is linked to this student."
                    else:
                        portal_session.login_as_parent(request, parent, student)
                        messages.success(
                            request,
                            f"Welcome, {parent.full_name}. Viewing {student.display_name}.",
                        )
                        return redirect(settings.PORTAL_LOGIN_REDIRECT_URL)

    preview_students = list(_eligible_students()[:40])
    return render(
        request,
        "portal/login.html",
        {
            "role": role,
            "error": error,
            "preview_students": preview_students,
            "student_count": _eligible_students().count(),
        },
    )


@require_GET
def student_search(request):
    """JSON endpoint for the login picker — keeps the page light on mobile."""
    q = (request.GET.get("q") or "").strip()
    qs = _eligible_students()
    if q:
        qs = qs.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(admission_number__icontains=q)
            | Q(assessment_number__icontains=q)
            | Q(class_group__icontains=q)
        )
    results = [
        {
            "id": s.pk,
            "name": s.display_name,
            "admission_number": s.admission_number or "—",
            "assessment_number": s.assessment_number,
            "level": s.academic_level_label,
            "class_group": s.class_group or "—",
            "parent": s.parent_guardian.full_name if s.parent_guardian_id else "—",
        }
        for s in qs[:25]
    ]
    return JsonResponse({"results": results})


@require_POST
@portal_session.portal_login_required
def logout_view(request):
    portal_session.clear_portal_session(request)
    request.session.flush()
    messages.info(request, "You have been signed out.")
    return redirect(settings.PORTAL_LOGIN_URL)


@portal_session.portal_login_required
@require_GET
def dashboard(request):
    student, denied = _portal_student_or_redirect(request)
    if denied:
        return denied

    return render(
        request,
        "portal/dashboard.html",
        {
            "student": student,
        },
    )


@portal_session.portal_login_required
@require_GET
def attendance(request):
    student, denied = _portal_student_or_redirect(request)
    if denied:
        return denied
    data = student_records.student_attendance(student)
    return render(
        request,
        "portal/attendance.html",
        {"student": student, **data},
    )


@portal_session.portal_login_required
@require_GET
def results(request):
    student, denied = _portal_student_or_redirect(request)
    if denied:
        return denied
    data = student_records.student_results(student)
    return render(
        request,
        "portal/results.html",
        {"student": student, **data},
    )


@portal_session.portal_login_required
@require_GET
def timetable(request):
    student, denied = _portal_student_or_redirect(request)
    if denied:
        return denied
    data = student_records.student_timetable(student)
    return render(
        request,
        "portal/timetable.html",
        {"student": student, **data},
    )


@portal_session.portal_login_required
@require_GET
def finances(request):
    student, denied = _portal_student_or_redirect(request)
    if denied:
        return denied
    data = student_finance_summary(student.pk)
    return render(
        request,
        "portal/finances.html",
        {"student": student, **data},
    )


@portal_session.portal_login_required
@require_GET
def elearning(request):
    student, denied = _portal_student_or_redirect(request)
    if denied:
        return denied
    data = elearning_service.student_elearning_subjects(student)
    return render(
        request,
        "portal/elearning.html",
        {"student": student, **data},
    )


@portal_session.portal_login_required
@require_GET
def elearning_subject(request, subject_id):
    student, denied = _portal_student_or_redirect(request)
    if denied:
        return denied
    data = elearning_service.student_elearning_subject(student, subject_id)
    if data is None:
        messages.error(request, "That subject is not available for this student.")
        return redirect("portal:elearning")
    return render(
        request,
        "portal/elearning_subject.html",
        {"student": student, **data},
    )


@require_POST
@portal_session.portal_login_required
def switch_student(request):
    """Parents can switch which linked child they are viewing."""
    if request.portal_role != portal_session.ROLE_PARENT or not request.portal_parent:
        messages.error(request, "Only parents can switch students.")
        return redirect(settings.PORTAL_LOGIN_REDIRECT_URL)

    student = get_object_or_404(
        Student,
        pk=request.POST.get("student_id"),
        parent_guardian_id=request.portal_parent.pk,
        is_suspended=False,
    )
    request.session[portal_session.SESSION_STUDENT_ID] = student.pk
    messages.success(request, f"Now viewing {student.display_name}.")

    next_url = (request.POST.get("next") or "").strip()
    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect(settings.PORTAL_LOGIN_REDIRECT_URL)
