"""Create missing support tables in the ACTIVE Flask SQLite database.

First performs a SQLite backup; does not alter existing table columns.
"""
import sqlite3
from datetime import datetime
from pathlib import Path

from app import app
from models import db
from support_tickets import SupportTicket, SupportMessage  # Register models
from sqlalchemy import inspect


def main():
    with app.app_context():
        if db.engine.dialect.name != "sqlite":
            raise SystemExit("This migration targets the existing SQLite deployment only.")
        source_path = Path(db.engine.url.database).resolve()
        if not source_path.is_file():
            raise SystemExit(f"Database not found: {source_path}. Stop; do not create a new one.")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = source_path.with_name(f"{source_path.stem}_before_support_{stamp}.db")
        with sqlite3.connect(str(source_path)) as source, sqlite3.connect(str(backup_path)) as backup:
            source.backup(backup)
        print("Backed up database to:", backup_path)
        db.create_all()
        tables = set(inspect(db.engine).get_table_names())
        if not {"support_ticket", "support_message"}.issubset(tables):
            raise SystemExit("Support tables missing. Check database permissions.")
        print("Support ticket tables ready. Existing records preserved.")


if __name__ == "__main__":
    main()
