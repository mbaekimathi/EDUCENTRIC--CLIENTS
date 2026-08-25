"""Session helpers for parent/student portal identity (not Django auth users)."""

from functools import wraps

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

from .models import ParentGuardian, Student

SESSION_ROLE = "portal_role"
SESSION_STUDENT_ID = "portal_student_id"
SESSION_PARENT_ID = "portal_parent_id"

ROLE_STUDENT = "student"
ROLE_PARENT = "parent"


def clear_portal_session(request):
    for key in (SESSION_ROLE, SESSION_STUDENT_ID, SESSION_PARENT_ID):
        request.session.pop(key, None)


def login_as_student(request, student: Student):
    clear_portal_session(request)
    request.session[SESSION_ROLE] = ROLE_STUDENT
    request.session[SESSION_STUDENT_ID] = student.pk
    request.session.cycle_key()


def login_as_parent(request, parent: ParentGuardian, student: Student | None = None):
    clear_portal_session(request)
    request.session[SESSION_ROLE] = ROLE_PARENT
    request.session[SESSION_PARENT_ID] = parent.pk
    if student is not None:
        request.session[SESSION_STUDENT_ID] = student.pk
    request.session.cycle_key()


def get_portal_role(request):
    return request.session.get(SESSION_ROLE)


def get_session_student(request):
    student_id = request.session.get(SESSION_STUDENT_ID)
    if not student_id:
        return None
    return (
        Student.objects.select_related("parent_guardian")
        .filter(pk=student_id, is_suspended=False)
        .first()
    )


def get_session_parent(request):
    parent_id = request.session.get(SESSION_PARENT_ID)
    if not parent_id:
        return None
    # Portal access is by linked student, not the admin "is_active" flag
    # (that flag is for future credentialed parent accounts).
    return ParentGuardian.objects.filter(pk=parent_id).first()


def portal_login_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not get_portal_role(request):
            return redirect(settings.PORTAL_LOGIN_URL)
        return view_func(request, *args, **kwargs)

    return _wrapped


def redirect_if_authenticated(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if get_portal_role(request):
            return redirect(settings.PORTAL_LOGIN_REDIRECT_URL)
        return view_func(request, *args, **kwargs)

    return _wrapped


def login_url():
    return reverse(settings.PORTAL_LOGIN_URL)
