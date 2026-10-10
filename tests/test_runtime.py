"""Basic Flask smoke test, run when dependencies are installed.

Uses the test runner's temporary environment/database; NEVER point this at your
real deployed Pharmacityville app or execute CI with production secrets.
"""
import importlib.util
import os
import unittest

@unittest.skipUnless(importlib.util.find_spec('flask') and importlib.util.find_spec('flask_sqlalchemy'), 'Flask dependencies not installed')
class FlaskAppSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['SECRET_KEY'] = 'unittest-only-do-not-deploy-this-placeholder'
        os.environ.pop('PUBLIC_BASE_URL', None)
        from app import app, seed_database
        cls.app = app
        seed_database(app)

    def test_catalog_is_public_and_lists_medicines(self):
        c = self.app.test_client()
        response = c.get('/medicines')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Alcohol Prep Pads', response.data)

    def test_homepage_and_admin_access(self):
        c = self.app.test_client()
        self.assertEqual(c.get('/').status_code, 200)
        # Admin-only view must not be accessible to an anonymous visitor.
        self.assertNotEqual(c.get('/admin/inventory-insights').status_code, 200)
