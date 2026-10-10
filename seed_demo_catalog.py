"""Add only missing demo products to an existing Pharmacityville database.

A new database is initialized with 54 demo medicines by `python app.py`.
This script never overwrites existing medicine records.

python seed_demo_catalog.py --check
python seed_demo_catalog.py --apply
"""
import argparse
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import sqlite3
from sqlalchemy import func
from app import app
from models import db, Medicine
from demo_catalog import full_demo_catalog

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    database = Path(app.instance_path) / 'pharmacityville.db'
    if not database.is_file():
        parser.error(f'Database not found: {database}. Initialize a new project with python app.py first.')
    with app.app_context():
        present = {row[0].casefold() for row in db.session.query(Medicine.name).all()}
        missing = [med for med in full_demo_catalog() if med['name'].casefold() not in present]
        print(f'Existing medicine records: {Medicine.query.count()}')
        print(f'Missing demonstration products: {len(missing)}')
        for med in missing:
            print('  +', med['name'])
        if args.check or not missing:
            print('No changes made.')
            return
        backup_file = database.parent / ('pharmacityville_backup_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.db')
        with sqlite3.connect(str(database)) as src, sqlite3.connect(str(backup_file)) as dst:
            src.backup(dst)
        print('Backup:', backup_file)
        try:
            for med in missing:
                db.session.add(Medicine(
                    name=med['name'], category=med['category'], price=Decimal(med['price']),
                    stock=med['stock'], description=med['description'],
                    requires_prescription=med['requires_prescription'], image_url=med['image_url']))
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        print(f'Added {len(missing)}. Total now: {Medicine.query.count()}')
        print('Existing products, orders, stock, payments, users were not edited.')

if __name__ == '__main__':
    main()
