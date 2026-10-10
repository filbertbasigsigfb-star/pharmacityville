"""Add 20 NEW sample medicines without modifying existing stock or prices.

Safe to re-run.  Prints how many entries were actually inserted.
"""
from decimal import Decimal
from app import app
from models import db, Medicine
from more_medicines import MORE_MEDICINES
from sqlalchemy import func


def main():
    added = 0
    with app.app_context():
        for item in MORE_MEDICINES:
            exists = Medicine.query.filter(func.lower(Medicine.name) == item["name"].lower()).first()
            if exists:
                continue
            db.session.add(Medicine(
                name=item["name"], category=item["category"],
                price=Decimal(item["price"]), stock=100,
                description=item["description"],
                requires_prescription=item["rx"],
                image_url=f'/static/img/medicines/{item["slug"]}.svg',
            ))
            added += 1
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        print(f"Added {added} new sample medicine(s). Total in inventory: {Medicine.query.count()}.")
        print("Existing medicine stock and prices were not modified.")


if __name__ == "__main__":
    main()
