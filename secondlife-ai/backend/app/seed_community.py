"""DEMO DATA ONLY: fills the dashboard with a plausible 12-week history of other makers.

Usage:  python -m app.seed --demo && python -m app.seed_community

These rows are invented for the demo so the dashboard is not empty. Accounts use
@secondlife.ai emails, which the dashboard detects and labels "includes demo accounts".
Do NOT present these numbers as real usage in your submission; say they are seeded.
Re-running does nothing if the community already exists.
"""
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .database import Base, SessionLocal, engine
from .models import BuildSession, Listing, Order, Project, User
from .security import hash_password

MAKERS = 14
WEEKS = 12
EMAIL = "maker{:02d}@secondlife.ai"
PASSWORD = "demo1234"

SALES = [  # category, label, specs, typical qty range, price in cents
    ("resistor", "220 ohm resistor", {"resistance_ohm": 220}, (5, 20), 150),
    ("resistor", "10k resistor", {"resistance_ohm": 10000}, (5, 20), 150),
    ("led", "Red LED", {"color": "red"}, (3, 12), 300),
    ("led", "Green LED", {"color": "green"}, (3, 12), 300),
    ("capacitor", "100uF 16V electrolytic", {"capacitance_uf": 100, "voltage_v": 16}, (2, 6), 800),
    ("transistor", "BC547 NPN", {"polarity": "npn", "part_number": "BC547"}, (2, 8), 500),
    ("potentiometer", "10k potentiometer", {"resistance_ohm": 10000}, (1, 3), 2500),
    ("battery", "9V battery", {"voltage_v": 9}, (1, 2), 3500),
    ("button", "Push button", {}, (2, 6), 500),
    ("buzzer", "Active buzzer 5V", {"buzzer_type": "active"}, (1, 3), 2500),
    ("ic", "NE555 timer", {"part_number": "NE555"}, (1, 3), 2500),
    ("microcontroller", "Arduino Nano", {"part_number": "ARDUINO NANO"}, (1, 1), 30000),
]


def main() -> None:
    Base.metadata.create_all(bind=engine)
    rng = random.Random(2026)
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        projects = db.scalars(select(Project)).all()
        if not projects:
            raise SystemExit("Run `python -m app.seed --demo` first (it loads the projects).")
        if db.scalar(select(User).where(User.email == EMAIL.format(1))):
            print("Community already seeded; nothing to do.")
            return

        pw = hash_password(PASSWORD)
        makers = []
        for i in range(1, MAKERS + 1):
            u = User(email=EMAIL.format(i), name=f"Maker {i:02d}", password_hash=pw,
                     created_at=now - timedelta(weeks=WEEKS, days=rng.randint(0, 6)))
            db.add(u)
            makers.append(u)
        db.commit()

        builds = sales = 0
        for w in range(WEEKS):  # w = 0 is the oldest week; activity grows over time
            week_start = now - timedelta(weeks=WEEKS - w)
            for _ in range(2 + w // 2 + rng.randint(0, 2)):
                when = week_start + timedelta(days=rng.random() * 6.5, hours=rng.randint(0, 12))
                if when > now:
                    when = now - timedelta(hours=rng.randint(1, 20))
                p = rng.choice(projects)
                db.add(BuildSession(user_id=rng.choice(makers).id, project_id=p.id,
                                    current_step=max(len(p.steps) - 1, 0), status="completed",
                                    created_at=when - timedelta(hours=1), updated_at=when))
                builds += 1
            for _ in range(3 + w // 2 + rng.randint(0, 3)):
                when = week_start + timedelta(days=rng.random() * 6.5, hours=rng.randint(0, 12))
                if when > now:
                    when = now - timedelta(hours=rng.randint(1, 20))
                cat, label, specs, (lo, hi), price = rng.choice(SALES)
                qty = rng.randint(lo, hi)
                seller, buyer = rng.sample(makers, 2)
                listing = Listing(seller_id=seller.id, category=cat, label=label, specs=specs, quantity=0,
                                  price_cents=price, condition="unverified", status="sold",
                                  created_at=when - timedelta(days=rng.randint(0, 3)))
                db.add(listing)
                db.flush()
                db.add(Order(buyer_id=buyer.id, listing_id=listing.id, quantity=qty, total_cents=price * qty,
                             status="completed", created_at=when))
                sales += 1
        # A few live listings so the marketplace and the activity feed look alive.
        for cat, label, specs, (lo, hi), price in rng.sample(SALES, 5):
            db.add(Listing(seller_id=rng.choice(makers).id, category=cat, label=label, specs=specs,
                           quantity=rng.randint(lo, hi), price_cents=price, condition="unverified", status="active",
                           created_at=now - timedelta(hours=rng.randint(1, 48))))
        db.commit()
        print(f"Seeded {MAKERS} demo makers, {builds} finished builds, {sales} sales (DEMO DATA).")


if __name__ == "__main__":
    main()
