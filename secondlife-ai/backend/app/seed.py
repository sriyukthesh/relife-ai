"""Seed projects (always) and a demo user with a realistic starter inventory (--demo).

Usage:  python -m app.seed [--demo]
"""
import json
import sys
from pathlib import Path

from sqlalchemy import select

from .database import Base, SessionLocal, engine
from .models import InventoryItem, Listing, Project, User
from .security import hash_password

DATA = Path(__file__).parent / "data" / "projects.json"

DEMO_EMAIL = "demo@secondlife.ai"
DEMO_PASSWORD = "demo1234"

# Designed so the demo shows: buildable now, one part away, and several missing.
DEMO_INVENTORY = [
    ("battery", "9V battery", {"voltage_v": 9}, 1, "tested_ok"),
    ("resistor", "220 ohm resistor", {"resistance_ohm": 220}, 4, "unverified"),
    ("resistor", "470 ohm resistor", {"resistance_ohm": 470}, 4, "unverified"),
    ("resistor", "10k resistor", {"resistance_ohm": 10000}, 3, "unverified"),
    ("led", "Red LED", {"color": "red"}, 3, "unverified"),
    ("led", "Green LED", {"color": "green"}, 2, "unverified"),
    ("led", "Yellow LED", {"color": "yellow"}, 1, "unverified"),
    ("transistor", "2N2222 NPN", {"polarity": "npn", "part_number": "2N2222"}, 2, "unverified"),
    ("ldr", "Light sensor (LDR)", {}, 1, "unverified"),
    ("button", "Push button", {}, 2, "tested_ok"),
    ("capacitor", "47uF 25V electrolytic", {"capacitance_uf": 47, "voltage_v": 25}, 2, "unverified"),
]


def seed_projects(db) -> int:
    count = 0
    for p in json.loads(DATA.read_text()):
        row = db.scalar(select(Project).where(Project.slug == p["slug"]))
        if row is None:
            row = Project(slug=p["slug"])
            db.add(row)
        row.title = p["title"]
        row.difficulty = p["difficulty"]
        row.estimated_minutes = p["estimated_minutes"]
        row.description = p["description"]
        row.safety_note = p.get("safety_note")
        row.requirements = p["requirements"]
        row.steps = p["steps"]
        count += 1
    db.commit()
    return count


def seed_demo(db) -> None:
    user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is None:
        user = User(email=DEMO_EMAIL, name="Demo Maker", password_hash=hash_password(DEMO_PASSWORD))
        db.add(user)
        db.commit()
    if db.scalar(select(InventoryItem).where(InventoryItem.user_id == user.id)) is None:
        for category, label, specs, qty, cond in DEMO_INVENTORY:
            db.add(InventoryItem(user_id=user.id, category=category, label=label, specs=specs,
                                 quantity=qty, condition=cond, source="manual"))
        db.commit()


SELLER_EMAIL = "seller@secondlife.ai"
SELLER_PASSWORD = "seller1234"

# Listings chosen to fill the gaps in the demo inventory.
# (category, label, specs, quantity, price in minor units, seller's condition claim)
SELLER_LISTINGS = [
    ("potentiometer", "10k potentiometer", {"resistance_ohm": 10000}, 2, 2500, "unverified"),
    ("ic", "NE555 timer", {"part_number": "NE555"}, 2, 3000, "tested_ok"),
    ("resistor", "47k resistor", {"resistance_ohm": 47000}, 10, 200, "unverified"),
    ("microcontroller", "Arduino Nano", {"part_number": "ARDUINO NANO"}, 1, 45000, "tested_ok"),
    ("buzzer", "Active buzzer 5V", {"buzzer_type": "active"}, 3, 3500, "unverified"),
    ("battery", "4x AA holder (6V)", {"voltage_v": 6}, 1, 6000, "unverified"),
    ("diode", "1N4007 diode", {"part_number": "1N4007"}, 5, 100, "unverified"),
]


def seed_marketplace(db) -> None:
    seller = db.scalar(select(User).where(User.email == SELLER_EMAIL))
    if seller is None:
        seller = User(email=SELLER_EMAIL, name="Priya (parts seller)", password_hash=hash_password(SELLER_PASSWORD))
        db.add(seller)
        db.commit()
    if db.scalar(select(Listing).where(Listing.seller_id == seller.id)) is None:
        for category, label, specs, qty, price, cond in SELLER_LISTINGS:
            db.add(Listing(seller_id=seller.id, category=category, label=label, specs=specs,
                           quantity=qty, price_cents=price, condition=cond, status="active"))
        db.commit()


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        print(f"Seeded {seed_projects(session)} projects")
        if "--demo" in sys.argv:
            seed_demo(session)
            seed_marketplace(session)
            print(f"Demo user: {DEMO_EMAIL} / {DEMO_PASSWORD}")
            print(f"Seller user: {SELLER_EMAIL} / {SELLER_PASSWORD}")
