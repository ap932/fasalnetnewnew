"""
Fasal-Net backend
==================

A single Flask app that:
  1. Serves the frontend pages (home.html, index.html, transporters.html)
     from the frontend/ folder, so every link works from ONE server/origin
     (this is almost always why "the pages don't link right" happens when
     you open them as separate local files instead of through a server).
  2. Exposes the JSON API the frontend already calls, backed by a real
     SQLite database (swap to Postgres for Render — see bottom of file).

Run locally:
    pip install -r requirements.txt
    python app.py
Then open http://127.0.0.1:5000/
"""

import os
from datetime import datetime, timezone

from flask import Flask, jsonify, request, send_from_directory
from flask_sqlalchemy import SQLAlchemy

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")

# ---------------------------------------------------------------------------
# Database config
# Uses SQLite by default (a single file, fasal_net.db, created automatically).
# On Render (or any host that gives you a Postgres DATABASE_URL), it's picked
# up automatically — no code changes needed.
# ---------------------------------------------------------------------------
db_url = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'fasal_net.db')}")
if db_url.startswith("postgres://"):  # Render gives old-style URLs; SQLAlchemy wants postgresql://
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class Farmer(db.Model):
    __tablename__ = "farmers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    contact = db.Column(db.String(20), nullable=False)
    location_text = db.Column(db.String(200), nullable=False)
    location_lat = db.Column(db.String(30), nullable=True)
    location_lng = db.Column(db.String(30), nullable=True)
    field_size_value = db.Column(db.Float, nullable=False)
    field_size_unit = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    crops = db.relationship("FarmerCrop", backref="farmer", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "contact": self.contact,
            "location": {"text": self.location_text, "lat": self.location_lat, "lng": self.location_lng},
            "fieldSize": {"value": self.field_size_value, "unit": self.field_size_unit},
            "crops": [c.to_dict() for c in self.crops],
            "createdAt": self.created_at.isoformat(),
        }


class FarmerCrop(db.Model):
    __tablename__ = "farmer_crops"

    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey("farmers.id"), nullable=False)
    crop = db.Column(db.String(80), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=False)

    def to_dict(self):
        return {"crop": self.crop, "quantity": self.quantity, "unit": self.unit}


class Transporter(db.Model):
    __tablename__ = "transporters"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    contact = db.Column(db.String(20), nullable=False)
    location_text = db.Column(db.String(200), nullable=False)
    location_lat = db.Column(db.String(30), nullable=True)
    location_lng = db.Column(db.String(30), nullable=True)
    min_price_per_tonne = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default="INR")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        # shape matches what transporters.html expects for the directory list
        return {
            "id": str(self.id),
            "name": self.name,
            "location": self.location_text,
            "contact": self.contact,
            "minPricePerTonne": self.min_price_per_tonne,
        }


class ContactRequest(db.Model):
    __tablename__ = "contact_requests"

    id = db.Column(db.Integer, primary_key=True)
    transporter_id = db.Column(db.Integer, db.ForeignKey("transporters.id"), nullable=False)
    farmer_name = db.Column(db.String(120), nullable=False)
    farmer_contact = db.Column(db.String(20), nullable=False)
    crop = db.Column(db.String(80), nullable=False)
    quantity_tonnes = db.Column(db.Float, nullable=False)
    message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "transporterId": self.transporter_id,
            "farmerName": self.farmer_name,
            "farmerContact": self.farmer_contact,
            "crop": self.crop,
            "quantityTonnes": self.quantity_tonnes,
            "message": self.message,
            "createdAt": self.created_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def bad_request(message):
    return jsonify({"error": message, "message": message}), 400


def require_fields(payload, fields):
    missing = [f for f in fields if payload.get(f) in (None, "", [])]
    return missing


# ---------------------------------------------------------------------------
# API routes — these match README.md / what the frontend already calls
# ---------------------------------------------------------------------------
@app.route("/api/farmers/register", methods=["POST"])
def register_farmer():
    payload = request.get_json(silent=True) or {}

    missing = require_fields(payload, ["name", "contact", "location", "fieldSize", "crops"])
    if missing:
        return bad_request(f"Missing field(s): {', '.join(missing)}")

    location = payload.get("location") or {}
    field_size = payload.get("fieldSize") or {}
    crops = payload.get("crops") or []

    if not location.get("text"):
        return bad_request("location.text is required")
    if field_size.get("value") is None or not field_size.get("unit"):
        return bad_request("fieldSize.value and fieldSize.unit are required")
    if not isinstance(crops, list) or len(crops) == 0:
        return bad_request("At least one crop is required")

    farmer = Farmer(
        name=payload["name"],
        contact=payload["contact"],
        location_text=location.get("text"),
        location_lat=location.get("lat"),
        location_lng=location.get("lng"),
        field_size_value=float(field_size["value"]),
        field_size_unit=field_size["unit"],
    )
    for c in crops:
        if not c.get("crop") or c.get("quantity") is None or not c.get("unit"):
            return bad_request("Each crop needs crop, quantity, and unit")
        farmer.crops.append(FarmerCrop(crop=c["crop"], quantity=float(c["quantity"]), unit=c["unit"]))

    db.session.add(farmer)
    db.session.commit()

    return jsonify({"id": farmer.id, "message": "Farmer registered"}), 201


@app.route("/api/transporters/register", methods=["POST"])
def register_transporter():
    payload = request.get_json(silent=True) or {}

    missing = require_fields(payload, ["name", "contact", "location", "minPricePerTonne"])
    if missing:
        return bad_request(f"Missing field(s): {', '.join(missing)}")

    location = payload.get("location") or {}
    if not location.get("text"):
        return bad_request("location.text is required")

    transporter = Transporter(
        name=payload["name"],
        contact=payload["contact"],
        location_text=location.get("text"),
        location_lat=location.get("lat"),
        location_lng=location.get("lng"),
        min_price_per_tonne=float(payload["minPricePerTonne"]),
        currency=payload.get("currency", "INR"),
    )
    db.session.add(transporter)
    db.session.commit()

    return jsonify({"id": transporter.id, "message": "Transporter registered"}), 201


@app.route("/api/transporters", methods=["GET"])
def list_transporters():
    query = Transporter.query

    location = request.args.get("location", "").strip()
    if location:
        query = query.filter(Transporter.location_text.ilike(f"%{location}%"))

    max_price = request.args.get("maxPrice", type=float)
    if max_price is not None:
        query = query.filter(Transporter.min_price_per_tonne <= max_price)

    sort = request.args.get("sort", "price-asc")
    if sort == "price-desc":
        query = query.order_by(Transporter.min_price_per_tonne.desc())
    elif sort == "name-asc":
        query = query.order_by(Transporter.name.asc())
    else:
        query = query.order_by(Transporter.min_price_per_tonne.asc())

    transporters = query.all()
    return jsonify([t.to_dict() for t in transporters])


@app.route("/api/transporters/<int:transporter_id>/requests", methods=["POST"])
def contact_transporter(transporter_id):
    transporter = Transporter.query.get(transporter_id)
    if transporter is None:
        return jsonify({"error": "Transporter not found", "message": "Transporter not found"}), 404

    payload = request.get_json(silent=True) or {}
    missing = require_fields(payload, ["farmerName", "farmerContact", "crop", "quantityTonnes"])
    if missing:
        return bad_request(f"Missing field(s): {', '.join(missing)}")

    contact_request = ContactRequest(
        transporter_id=transporter.id,
        farmer_name=payload["farmerName"],
        farmer_contact=payload["farmerContact"],
        crop=payload["crop"],
        quantity_tonnes=float(payload["quantityTonnes"]),
        message=payload.get("message", ""),
    )
    db.session.add(contact_request)
    db.session.commit()

    return jsonify({"id": contact_request.id, "message": "Request sent"}), 201


# ---------------------------------------------------------------------------
# Price prediction & crop suggestions
#
# PLACEHOLDER LOGIC — this is a deterministic heuristic, not a trained model.
# It exists so insights.html has something real to call instead of failing.
# Swap the body of these two functions for your actual AI/ML component
# (the one described in the project synopsis) — the request/response shapes
# below are the contract the frontend already expects, so nothing else needs
# to change when you plug in the real model.
# ---------------------------------------------------------------------------
_BASE_CROP_PRICES = {
    "wheat": 2140, "rice": 2600, "maize": 1900, "bajra": 2200, "jowar": 2450,
    "sugarcane": 340, "cotton": 6800, "soybean": 4300, "mustard": 5400,
    "gram": 5100, "groundnut": 5850, "barley": 1850,
}


def _estimate_price(crop):
    key = crop.strip().lower()
    base = _BASE_CROP_PRICES.get(key)
    if base is None:
        # unknown crop: derive a stable pseudo-price from its name so repeated
        # lookups are at least consistent, and flag it as low confidence
        base = 1800 + (sum(ord(c) for c in key) % 900)
    return base, key in _BASE_CROP_PRICES


@app.route("/api/price-prediction", methods=["GET"])
def price_prediction():
    crop = request.args.get("crop", "").strip()
    location = request.args.get("location", "").strip()
    if not crop or not location:
        return bad_request("crop and location query params are required")

    base_price, known = _estimate_price(crop)

    nearby_markets = [
        {"market": f"{location} mandi", "distanceKm": 6, "price": base_price + 20},
        {"market": f"{location} (secondary market)", "distanceKm": 18, "price": base_price - 25},
        {"market": "Regional wholesale hub", "distanceKm": 42, "price": base_price + 60},
    ]

    return jsonify({
        "crop": crop,
        "unit": "quintal",
        "predictedPrice": base_price,
        "confidence": "Medium confidence" if known else "Low confidence — unfamiliar crop name",
        "range": {"low": round(base_price * 0.92), "high": round(base_price * 1.08)},
        "nearbyMarkets": nearby_markets,
    })


_SUGGESTION_POOL = [
    {"crop": "Mustard", "fit": "high", "reason": "Low water need, fits a typical rabi season, steady recent demand.", "tags": ["Low water", "Rabi season"]},
    {"crop": "Gram", "fit": "high", "reason": "Improves soil nitrogen, works well as a rotation partner, reliable local buyers.", "tags": ["Soil health", "Rotation crop"]},
    {"crop": "Bajra", "fit": "medium", "reason": "Drought-tolerant option if rainfall has been unpredictable this season.", "tags": ["Drought tolerant"]},
    {"crop": "Groundnut", "fit": "medium", "reason": "Good oilseed demand and a reasonable fit for lighter soils.", "tags": ["Oilseed demand"]},
]


@app.route("/api/crop-suggestions", methods=["GET"])
def crop_suggestions():
    location = request.args.get("location", "").strip()
    field_size = request.args.get("fieldSize", type=float)
    if not location or field_size is None:
        return bad_request("location and fieldSize query params are required")

    suggestions = []
    for item in _SUGGESTION_POOL:
        base_price, _ = _estimate_price(item["crop"])
        suggestions.append({**item, "estPricePerQuintal": base_price})

    return jsonify(suggestions)


# ---------------------------------------------------------------------------
# Frontend routes — serves home.html / index.html / transporters.html
# from the frontend/ folder so all the <a href="..."> links resolve
# against the SAME origin as the API (this is what fixes cross-page
# navigation when it doesn't work from opening files directly).
# ---------------------------------------------------------------------------
@app.route("/")
def serve_home():
    return send_from_directory(FRONTEND_DIR, "home.html")


@app.route("/<path:filename>")
def serve_frontend_file(filename):
    return send_from_directory(FRONTEND_DIR, filename)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
