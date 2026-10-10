"""Idempotently add 20 illustrative medicines without touching existing stock."""
from app import app
from models import Medicine, db
from medicine_data import EXTRA_MEDICINES
from decimal import Decimal
from sqlalchemy import func

with app.app_context():
    names = {x[0].casefold() for x in db.session.query(Medicine.name).all()}
    added = 0
    for item in EXTRA_MEDICINES:
        if item["name"].casefold() in names:
            continue
        db.session.add(Medicine(
            name=item["name"], category=item["category"],
            price=Decimal(item["price"]), stock=100,
            description=item["description"], image_url=item["image_url"],
            requires_prescription=item["requires_prescription"],
        ))
        names.add(item["name"].casefold())
        added += 1
    db.session.commit()
    print(f"Added {added} medicines; {len(EXTRA_MEDICINES)-added} already existed.")
    print(f"Total medicines: {Medicine.query.count()}")
