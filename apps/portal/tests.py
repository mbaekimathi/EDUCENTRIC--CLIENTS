from django.contrib.sessions.exceptions import SessionInterrupted
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

from apps.portal.middleware import SessionInterruptedMiddleware


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
