"""
Seed the database with a handful of sample transporters (and one farmer)
so transporters.html has real rates to display right away.

Run this AFTER app.py has created the database at least once:
    python app.py            (start it once, then stop it — Ctrl+C)
    python seed_db.py
"""

from app import app, db, Transporter, Farmer, FarmerCrop

SAMPLE_TRANSPORTERS = [
    {"name": "Suresh Transport Co.", "contact": "9123456780", "location_text": "Hisar, Haryana", "min_price_per_tonne": 1800},
    {"name": "Bhandari Carriers", "contact": "9988776655", "location_text": "Barwala, Hisar", "min_price_per_tonne": 1650},
    {"name": "Om Sai Roadways", "contact": "9871234560", "location_text": "Sirsa, Haryana", "min_price_per_tonne": 2000},
    {"name": "Kisan Freight Line", "contact": "9012345678", "location_text": "Hisar, Haryana", "min_price_per_tonne": 1720},
    {"name": "Rathi Logistics", "contact": "9345612780", "location_text": "Fatehabad, Haryana", "min_price_per_tonne": 1900},
    {"name": "Malik Transport", "contact": "9765432109", "location_text": "Barwala, Hisar", "min_price_per_tonne": 1580},
]

with app.app_context():
    db.create_all()

    if Transporter.query.count() > 0:
        print(f"Database already has {Transporter.query.count()} transporter(s) — skipping seed.")
    else:
        for t in SAMPLE_TRANSPORTERS:
            db.session.add(Transporter(
                name=t["name"], contact=t["contact"],
                location_text=t["location_text"], min_price_per_tonne=t["min_price_per_tonne"],
            ))
        db.session.commit()
        print(f"Seeded {len(SAMPLE_TRANSPORTERS)} transporters.")

    if Farmer.query.count() == 0:
        farmer = Farmer(
            name="Ramesh Kumar", contact="9876543210",
            location_text="Barwala, Hisar, Haryana",
            field_size_value=4.5, field_size_unit="acre",
        )
        farmer.crops.append(FarmerCrop(crop="Wheat", quantity=40, unit="quintal"))
        db.session.add(farmer)
        db.session.commit()
        print("Seeded 1 sample farmer.")
