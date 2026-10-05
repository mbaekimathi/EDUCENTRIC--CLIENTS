from django.contrib.sessions.exceptions import SessionInterrupted
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

from apps.portal.middleware import (
    ResilientSessionMiddleware,
    SessionInterruptedMiddleware,
)


class SessionInterruptedMiddlewareTests(SimpleTestCase):
    def test_redirects_to_login_and_clears_cookie(self):
        def boom(_request):
            raise SessionInterrupted("session gone")

        middleware = SessionInterruptedMiddleware(boom)
        request = RequestFactory().get("/")

        with override_settings(SESSION_COOKIE_NAME="edu_clients_sessionid"):
            response = middleware(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("portal:login"))
        cookie = response.cookies.get("edu_clients_sessionid")
        self.assertIsNotNone(cookie)
        self.assertEqual(cookie.value, "")

    def test_passes_through_normal_responses(self):
        middleware = SessionInterruptedMiddleware(lambda _r: HttpResponse("ok"))
        response = middleware(RequestFactory().get("/"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")


class ResilientSessionMiddlewareTests(SimpleTestCase):
    def test_process_response_clears_cookie_on_session_interrupted(self):
        middleware = ResilientSessionMiddleware(lambda _r: HttpResponse("login ok"))
        request = RequestFactory().get("/")
        request.session = type("S", (), {"accessed": False, "modified": False})()

        original = SessionMiddleware.process_response

        def raise_interrupted(self, request, response):
            raise SessionInterrupted("session gone")

        SessionMiddleware.process_response = raise_interrupted
        try:
            with override_settings(SESSION_COOKIE_NAME="edu_clients_sessionid"):
                response = middleware.process_response(request, HttpResponse("login ok"))
        finally:
            SessionMiddleware.process_response = original

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"login ok")
        cookie = response.cookies.get("edu_clients_sessionid")
        self.assertIsNotNone(cookie)
        self.assertEqual(cookie.value, "")
