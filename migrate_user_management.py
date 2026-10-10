"""One-time safe SQLite schema update for User Management.

Run ONCE before reloading the updated web app:
    python migrate_user_management.py

This script is repeatable. It does not delete accounts, orders, or medicines.
"""
from datetime import datetime
from pathlib import Path
import sqlite3

from app import app
from models import db


def migrate():
    db_file = Path(app.instance_path) / "pharmacityville.db"
    db_file.parent.mkdir(parents=True, exist_ok=True)

    if db_file.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup = db_file.with_name(f"pharmacityville.before-users-{stamp}.db")
        with sqlite3.connect(str(db_file)) as source:
            with sqlite3.connect(str(backup)) as target:
                source.backup(target)
        print(f"Backup saved: {backup}")

    with app.app_context():
        # New database? Just create the full schema directly.
        db.create_all()

        # Existing database created by an earlier version of models.py?
        with sqlite3.connect(str(db_file)) as conn:
            columns = {row[1] for row in conn.execute('PRAGMA table_info("user")')}
            if "is_enabled" not in columns:
                conn.execute('ALTER TABLE "user" ADD COLUMN is_enabled BOOLEAN NOT NULL DEFAULT 1')
                conn.commit()
                print("Added 'is_enabled' to existing users (all enabled by default).")
            else:
                print("User Management schema already present; nothing to change.")

    print("Migration finished. Existing account IDs and history were preserved.")


if __name__ == "__main__":
    migrate()
