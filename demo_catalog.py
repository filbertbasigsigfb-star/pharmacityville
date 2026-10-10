"""Combined 54-medicine demonstration catalog and locally bundled picture mapping.

Product prices, images and descriptions are school-project examples, not
real pharmacy inventory or dispensing information.
"""
import json
from pathlib import Path
from medicine_data import SAMPLE_MEDICINES, EXTRA_MEDICINES
from more_medicines import MORE_MEDICINES

def full_demo_catalog():
    mapping = json.loads((Path(__file__).resolve().parent / 'catalog_images.json').read_text(encoding='utf-8'))
    items = [dict(m) for m in SAMPLE_MEDICINES + EXTRA_MEDICINES]
    for m in MORE_MEDICINES:
        items.append({
            'name': m['name'], 'category': m['category'], 'price': m['price'],
            'stock': 100, 'requires_prescription': m['rx'],
            'description': m['description'],
            'image_url': f"/static/img/medicines/{m['slug']}.svg",
        })
    for medicine in items:
        override = mapping.get(medicine['name'])
        if override:
            medicine['image_url'] = override['image']
            if override['tablet']:
                medicine['description'] = 'Per piece'
    names = [m['name'].casefold() for m in items]
    if len(items) != 54 or len(set(names)) != 54:
        raise ValueError('Expected 54 distinct demonstration medicines')
    return items
