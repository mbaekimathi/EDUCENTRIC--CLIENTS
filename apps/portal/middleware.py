from . import session as portal_session


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
