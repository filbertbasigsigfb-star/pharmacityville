"""20 additional illustrative products for the Pharmacityville school demo.

Prices, prescription flags and availability are sample values ONLY. They are
not real pharmacy advice or local dispensing determinations.
"""
MORE_MEDICINES = [
    {"name": "Vitamin B12 500mcg", "category": "Vitamins", "price": "10.00", "description": "Illustrative vitamin B12 supplement tablets.", "rx": False, "slug": "vitamin-b12-500mcg"},
    {"name": "Vitamin E 400 IU", "category": "Vitamins", "price": "12.50", "description": "Illustrative vitamin E softgel supplement.", "rx": False, "slug": "vitamin-e-400iu"},
    {"name": "Calcium + Vitamin D Tablets", "category": "Vitamins", "price": "14.00", "description": "Illustrative calcium and vitamin D supplement.", "rx": False, "slug": "calcium-vitamin-d-tablets"},
    {"name": "Omega-3 Softgels 1000mg", "category": "Vitamins", "price": "18.00", "description": "Illustrative omega-3 fish oil supplement.", "rx": False, "slug": "omega-3-softgels-1000mg"},
    {"name": "Vitamin C Chewable 250mg", "category": "Vitamins", "price": "6.00", "description": "Illustrative chewable vitamin C tablets.", "rx": False, "slug": "vitamin-c-chewable-250mg"},
    {"name": "Oral Zinc 20mg", "category": "Vitamins", "price": "6.50", "description": "Illustrative oral zinc supplement.", "rx": False, "slug": "oral-zinc-20mg"},
    {"name": "Guaifenesin Syrup 100mg/5mL", "category": "Cold & Flu", "price": "45.00", "description": "Illustrative expectorant syrup; follow product labeling and pharmacist guidance.", "rx": True, "slug": "guaifenesin-syrup"},
    {"name": "Dextromethorphan Syrup 10mg/5mL", "category": "Cold & Flu", "price": "52.00", "description": "Illustrative cough suppressant syrup; availability and regulations vary.", "rx": True, "slug": "dextromethorphan-syrup"},
    {"name": "Loperamide 2mg", "category": "Digestive Health", "price": "7.00", "description": "Illustrative antidiarrheal medicine.", "rx": False, "slug": "loperamide-2mg"},
    {"name": "Bisacodyl 5mg", "category": "Digestive Health", "price": "8.00", "description": "Illustrative stimulant laxative tablets.", "rx": False, "slug": "bisacodyl-5mg"},
    {"name": "Senna Tablets", "category": "Digestive Health", "price": "6.50", "description": "Illustrative senna laxative tablets.", "rx": False, "slug": "senna-tablets"},
    {"name": "Clotrimazole Cream 1%", "category": "Skin Care", "price": "55.00", "description": "Illustrative antifungal skin cream; ask a pharmacist before use.", "rx": False, "slug": "clotrimazole-cream-1"},
    {"name": "Calamine Lotion", "category": "Skin Care", "price": "48.00", "description": "Illustrative soothing skin lotion.", "rx": False, "slug": "calamine-lotion"},
    {"name": "Benzoyl Peroxide Gel 2.5%", "category": "Skin Care", "price": "85.00", "description": "Illustrative acne care gel.", "rx": False, "slug": "benzoyl-peroxide-gel"},
    {"name": "Salicylic Acid Acne Gel 2%", "category": "Skin Care", "price": "76.00", "description": "Illustrative acne skin-care gel.", "rx": False, "slug": "salicylic-acid-acne-gel"},
    {"name": "Glycerin Suppositories", "category": "Digestive Health", "price": "35.00", "description": "Illustrative glycerin suppositories; consult product instructions.", "rx": False, "slug": "glycerin-suppositories"},
    {"name": "Antiseptic Mouthwash 250mL", "category": "Oral Care", "price": "59.00", "description": "Illustrative antiseptic oral rinse; formulation varies.", "rx": False, "slug": "antiseptic-mouthwash"},
    {"name": "Menthol Nasal Inhaler", "category": "Cold & Flu", "price": "23.00", "description": "Illustrative menthol nasal inhaler.", "rx": False, "slug": "menthol-nasal-inhaler"},
    {"name": "Alcohol Prep Pads 100-Pack", "category": "First Aid", "price": "65.00", "description": "Illustrative first-aid alcohol prep pads for external use.", "rx": False, "slug": "alcohol-prep-pads"},
    {"name": "Nitrile Gloves 50-Pack", "category": "Health Essentials", "price": "120.00", "description": "Illustrative powder-free disposable nitrile gloves.", "rx": False, "slug": "nitrile-gloves"},
]
assert len(MORE_MEDICINES) == 20
