"""No external dependencies: python -m unittest discover -s tests"""
import ast
import json
import subprocess
from pathlib import Path, PurePosixPath
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
        # Check files COMMITTED to Git, not temporary data made by Flask tests.
        # The runtime tests legitimately create instance/pharmacityville.db.
        result = subprocess.run(
            ["git", "ls-files", "-z", "--cached"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        tracked = [
            PurePosixPath(path.decode("utf-8", "surrogateescape"))
            for path in result.stdout.split(b"\\0") if path
        ]
        forbidden = []
        for path in tracked:
            name = path.name.lower()
            if (
                name == ".env"
                or (name.startswith(".env.") and name != ".env.example")
                or name.endswith((".db", ".sqlite", ".sqlite3", ".db-wal",
                                  ".db-shm", ".db-journal"))
            ):
                forbidden.append(str(path))
        self.assertEqual(
            forbidden, [],
            "Private environment files or database files are tracked: "
            + ", ".join(forbidden),
        )
    def test_core_app_files_present(self):
        for file in ['app.py','models.py','auth.py','payments.py','inventory_insights.py','templates/base.html','templates/catalog.html']:
            self.assertTrue((ROOT/file).is_file())
