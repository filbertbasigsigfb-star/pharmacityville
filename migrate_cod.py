"""One-time, repeatable migration to add COD fields to the existing SQLite order table.

Does not create a new empty database if the existing project DB is missing.
Uses SQLite's online backup API before changing the schema.
"""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).resolve().parent / "instance" / "pharmacityville.db"
if not DB_PATH.is_file():
    raise SystemExit(f"Database does not exist: {DB_PATH}. Check your PythonAnywhere project path.")

conn = sqlite3.connect(DB_PATH, timeout=20)
try:
    table = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='order'").fetchone()
    if not table:
        raise SystemExit("Existing order table not found; stopping without changes.")

    # Keep the backup even if a later migration step fails.
    backup_path = DB_PATH.with_name(
        f"pharmacityville_before_cod_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}.db"
    )
    with sqlite3.connect(backup_path) as dest:
        conn.backup(dest)
    print(f"Backup created: {backup_path}")

    old_columns = {column[1] for column in conn.execute('PRAGMA table_info("order")')}
    additions = {
        "payment_method": "VARCHAR(20) NOT NULL DEFAULT 'pickup'",
        "delivery_name": "VARCHAR(100)",
        "delivery_phone": "VARCHAR(20)",
        "delivery_address": "VARCHAR(500)",
        "cod_paid_at": "DATETIME",
    }
    for name, sql_type in additions.items():
        if name not in old_columns:
            conn.execute(f'ALTER TABLE "order" ADD COLUMN {name} {sql_type}')
            print("Added column:", name)
        else:
            print("Already exists:", name)
    conn.commit()
    print("COD migration complete. Existing orders and medicines are preserved.")
finally:
    conn.close()
