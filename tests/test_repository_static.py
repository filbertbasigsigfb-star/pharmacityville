"""No external dependencies: python -m unittest discover -s tests"""
import ast
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
class RepositoryStaticTests(unittest.TestCase):
    def test_all_python_files_parse(self):
        for path in ROOT.glob('*.py'):
            with self.subTest(file=path.name):
                ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    def test_40_demo_image_links_exist(self):
        mapping=json.loads((ROOT/'catalog_images.json').read_text(encoding='utf-8'))
        self.assertEqual(len(mapping),40)
        for name, entry in mapping.items():
            with self.subTest(medicine=name):
                self.assertTrue((ROOT / entry['image'].lstrip('/')).is_file())
    def test_no_database_or_real_env_in_repo(self):
        self.assertFalse((ROOT/'.env').exists())
        self.assertFalse(any(ROOT.rglob('*.db')))
    def test_core_app_files_present(self):
        for file in ['app.py','models.py','auth.py','payments.py','inventory_insights.py','templates/base.html','templates/catalog.html']:
            self.assertTrue((ROOT/file).is_file())
