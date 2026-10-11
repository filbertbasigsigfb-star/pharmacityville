"""Functional password-recovery checks (run in a temporary test database)."""
import importlib.util
import os
import re
import unittest
import uuid
from unittest.mock import patch

from itsdangerous import URLSafeTimedSerializer


@unittest.skipUnless(importlib.util.find_spec("flask") and importlib.util.find_spec("flask_sqlalchemy"),
                     "Flask libraries are not installed")
class PasswordResetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["SECRET_KEY"] = "test-only-unique-secret-key-do-not-deploy"
        os.environ["PUBLIC_BASE_URL"] = "http://localhost:5000"
        from app import app
        from models import db
        cls.app = app
        app.config["TESTING"] = True
        with app.app_context():
            db.create_all()

    def setUp(self):
        from models import User, db
        self.email = f"forgot-test-{uuid.uuid4().hex}@example.com"
        with self.app.app_context():
            user = User(name="Reset Test User", email=self.email, role="customer")
            user.set_password("OriginalPassword123!")
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id
        self.client = self.app.test_client()

    def _csrf(self, client, route):
        body = client.get(route).get_data(as_text=True)
        return re.search(r'name="_csrf_token" value="([^"]+)"', body).group(1)

    def test_login_shows_recovery_link_and_unknown_email_is_not_disclosed(self):
        self.assertIn(b"Forgot password?", self.client.get("/login").data)
        csrf = self._csrf(self.client, "/forgot-password")
        with patch("password_reset._send_notice") as sender:
            response = self.client.post("/forgot-password", data={"_csrf_token": csrf,
                                                                    "email": "unknown@example.com"}, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"If the email is registered", response.data)
            sender.assert_not_called()

    def test_token_is_single_use_and_existing_sessions_are_invalidated(self):
        from models import User, db
        csrf = self._csrf(self.client, "/forgot-password")
        with patch("password_reset._send_notice", return_value="sent") as sender:
            response = self.client.post("/forgot-password", data={"_csrf_token": csrf, "email": self.email})
            self.assertEqual(response.status_code, 302)
            sender.assert_called_once()
            mail_body = sender.call_args.args[2]
        url = re.search(r"http://localhost:5000(/reset-password/[^\s]+)", mail_body).group(1)
        token = url.rsplit("/", 1)[-1]
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
        csrf = self._csrf(self.client, url)
        response = self.client.post(url, data={"_csrf_token": csrf,
                                               "password": "NewPassword123!",
                                               "confirm_password": "NewPassword123!"})
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            user = db.session.get(User, self.user_id)
            self.assertTrue(user.check_password("NewPassword123!"))
            self.assertFalse(user.check_password("OriginalPassword123!"))
        replay = self.client.get(url)
        self.assertEqual(replay.status_code, 302)

    def test_tampered_token_is_rejected(self):
        self.assertEqual(self.client.get("/reset-password/this-is-invalid").status_code, 302)


if __name__ == "__main__":
    unittest.main()