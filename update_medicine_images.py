"""One-time, safe inventory update for existing Pharmacityville databases.

Run: python update_medicine_images.py
Optional: python update_medicine_images.py --replace-images

Does not delete or change existing medicines' prices, stock, or orders.
The default only fills blank image URLs; --replace-images replaces images
for the 14 named demo medicines, without modifying custom medicines.
"""
import argparse
from decimal import Decimal
from app import app
from medicine_data import SAMPLE_MEDICINES, ORIGINAL_MEDICINE_COUNT
from models import db, Medicine


def main():
    parser = argparse.ArgumentParser(description="Add six demo medicines and local medicine images")
    parser.add_argument(
        "--replace-images", action="store_true",
        help="Replace existing image links for the 14 named demo medicines"
    )
    args = parser.parse_args()

    created = 0
    updated_images = 0
    unchanged = 0

    with app.app_context():
        # Do not create a second database or alter existing tables.
        db.create_all()
        try:
            existing = {m.name.strip().casefold(): m for m in Medicine.query.all()}

            for index, item in enumerate(SAMPLE_MEDICINES):
                key = item["name"].casefold()
                medicine = existing.get(key)

                if medicine is None:
                    # Only add the SIX new samples. We do not restore older
                    # medicines an administrator may have deliberately deleted.
                    if index < ORIGINAL_MEDICINE_COUNT:
                        continue

                    medicine = Medicine(
                        name=item["name"],
                        category=item["category"],
                        price=Decimal(item["price"]),
                        stock=item["stock"],
                        description=item["description"],
                        requires_prescription=item["requires_prescription"],
                        image_url=item["image_url"],
                    )
                    db.session.add(medicine)
                    created += 1
                elif args.replace_images or not (medicine.image_url or "").strip():
                    if medicine.image_url != item["image_url"]:
                        medicine.image_url = item["image_url"]
                        updated_images += 1
                else:
                    unchanged += 1

            db.session.commit()

        except Exception:
            db.session.rollback()
            raise

        print(f"Added new medicines: {created}")
        print(f"Updated image links: {updated_images}")
        print(f"Preserved existing image links: {unchanged}")
        print(f"Total medicines in database: {Medicine.query.count()}")
        print("The existing prices, stock counts, and orders were preserved.")


if __name__ == "__main__":
    main()
