import time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings

from apps.accounts.middleware import SessionInactivityMiddleware


@override_settings(SESSION_COOKIE_AGE=3600)
class SessionInactivityMiddlewareTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="idle@test.local",
            password="secret",
            is_staff=True,
        )
        self.factory = RequestFactory()
        self.middleware = SessionInactivityMiddleware(lambda r: None)

    def test_logs_out_after_idle_timeout(self):
        request = self.factory.get("/admin/")
        request.user = self.user
        request.session = self.client.session
        self.client.force_login(self.user)
        request.session = self.client.session
        request.session["_finance_last_activity"] = int(time.time()) - 7200

        response = self.middleware.process_request(request)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 302)

    def test_refreshes_activity_on_request(self):
        request = self.factory.get("/admin/finance/dashboard/")
        self.client.force_login(self.user)
        request.user = self.user
        request.session = self.client.session
        request.session["_finance_last_activity"] = int(time.time()) - 10

        with patch("apps.accounts.middleware.logout") as mock_logout:
            response = self.middleware.process_request(request)
        self.assertIsNone(response)
        mock_logout.assert_not_called()
        self.assertIn("_finance_last_activity", request.session)
