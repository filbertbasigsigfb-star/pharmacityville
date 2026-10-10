"""Read-only smoke check for the upgraded PythonAnywhere project."""
from pathlib import Path
from sqlalchemy import inspect
from app import app
from models import Medicine, db
from more_medicines import MORE_MEDICINES


with app.app_context():
    tables = set(inspect(db.engine).get_table_names())
    rules = {(r.rule, tuple(sorted(r.methods))) for r in app.url_map.iter_rules()}
    has_routes = (
        any(route == "/support/new" for route, _ in rules) and
        any(route == "/admin/support/" for route, _ in rules)
    )
    pictures = all((Path(__file__).resolve().parent / "static/img/medicines" / (item["slug"] + ".svg")).is_file() for item in MORE_MEDICINES)
    print("Customer + admin report routes:", "OK" if has_routes else "MISSING")
    print("Support tables:", "OK" if {"support_ticket", "support_message"}.issubset(tables) else "MISSING")
    print("20 local medicine illustrations:", "OK" if pictures else "MISSING")
    print("Medicine inventory total:", Medicine.query.count())
    print("Bulk restock route:", "OK" if any(route == "/admin/medicines/restock" for route, _ in rules) else "MISSING")
