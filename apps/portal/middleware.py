from django.conf import settings
from django.contrib.sessions.exceptions import SessionInterrupted
from django.contrib.sessions.middleware import SessionMiddleware
from django.shortcuts import redirect

from . import session as portal_session


def _clear_session_cookie(response):
    response.delete_cookie(
        settings.SESSION_COOKIE_NAME,
        path=getattr(settings, "SESSION_COOKIE_PATH", "/"),
        domain=getattr(settings, "SESSION_COOKIE_DOMAIN", None),
        samesite=getattr(settings, "SESSION_COOKIE_SAMESITE", "Lax"),
    )
    return response


class ResilientSessionMiddleware(SessionMiddleware):
    """
    SessionMiddleware that survives a mid-request session delete.

    On cPanel, cached_db + FileBasedCache can serve a ghost session after
    logout flushed the DB row. CSRF/messages then mark the session modified,
    save() raises UpdateError, and Django turns that into SessionInterrupted.
    Drop the stale cookie and return the already-built response instead.
    """

    def process_response(self, request, response):
        try:
            return super().process_response(request, response)
        except SessionInterrupted:
            return _clear_session_cookie(response)


class SessionInterruptedMiddleware:
    """
    Safety net outside SessionMiddleware for any SessionInterrupted that
    still propagates (e.g. older deploys / unexpected raise sites).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except SessionInterrupted:
            return _clear_session_cookie(redirect(settings.PORTAL_LOGIN_URL))


class PortalSessionMiddleware:
    """Attach portal identity to each request for templates and views."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.portal_role = portal_session.get_portal_role(request)
        request.portal_student = None
        request.portal_parent = None

        if request.portal_role == portal_session.ROLE_STUDENT:
            request.portal_student = portal_session.get_session_student(request)
            if request.portal_student is None:
                portal_session.clear_portal_session(request)
                request.portal_role = None
        elif request.portal_role == portal_session.ROLE_PARENT:
            request.portal_parent = portal_session.get_session_parent(request)
            request.portal_student = portal_session.get_session_student(request)
            # Parent sessions need a valid guardian and a selected child.
            if request.portal_parent is None or request.portal_student is None:
                portal_session.clear_portal_session(request)
                request.portal_role = None
                request.portal_parent = None
                request.portal_student = None

        return self.get_response(request)
