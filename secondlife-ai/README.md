# SecondLife AI

Point a camera at salvaged electronics; get identified parts, confirmed inventory, and projects you can build today.

## Phase 1 (this drop): backend foundation
PostgreSQL schema, unified login, confirmed-only inventory, deterministic project engine,
8 curated projects, demo seed data, engine tests.

### Run it
```bash
docker compose up -d db
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                    # Windows: copy .env.example .env
python -m app.seed --demo                               # projects + demo user (demo@secondlife.ai / demo1234)
uvicorn app.main:app --reload
```
Open http://localhost:8000/docs, click **Authorize** after `POST /auth/login`, then try
`GET /recommendations`. Run tests with `pytest`.

### Key design rules (enforced in code)
- `POST /inventory` rejects anything without `confirmed_by_user: true`.
- Parts missing required specs, or marked `suspect_damaged`, are never used for projects.
- Unverified parts are usable but flagged "test before use".
- Capacitor/battery voltage and resistor ranges are checked per project requirement.

## Roadmap
- Phase 2: Meta Model API client, SAM 3.1 + Muse Spark inspection endpoint
- Phase 3: Build sessions, copilot, Muse Voice Transcribe
- Phase 4: Frontend (React/Vite/Tailwind): auth, inventory, scan + confirm
- Phase 5: Frontend: recommendations, build copilot (voice), marketplace
- Phase 6: Accuracy evaluation script, demo script, submission text


## Phase 2 + 3 additions (backend)

Run order: `docker compose up -d` -> `cd backend && pip install -r requirements.txt` -> copy `.env.example` to `.env` and set `MODEL_API_KEY` and `MUSE_MODEL` -> `python -m app.seed --demo` -> `uvicorn app.main:app --reload`.

| Area | Endpoints |
|---|---|
| Photo -> proposals (nothing saved) | `POST /inspect` |
| Confirmed inventory | `POST /inventory` (needs `confirmed_by_user: true`) |
| Build with What I Have | `GET /recommendations` |
| Guided build | `POST /builds`, `GET /builds/current`, `POST /builds/{id}/next|previous|finish` |
| Copilot | `POST /copilot/ask` |
| Marketplace | `GET/POST /marketplace/listings`, `DELETE /marketplace/listings/{id}`, `POST /marketplace/listings/{id}/buy`, `GET /marketplace/orders`, `GET /marketplace/for-project/{slug}` |

Checks, in this order:
1. `pytest`
2. `python scripts/test_muse.py` then `python scripts/test_muse.py photo.jpg`
3. `python scripts/evaluate.py --photos eval/photos --truth eval/truth.csv` (see `eval/truth.example.csv`)

Rules enforced in code: output is only a proposal; `tested_ok` is never suggested; suspect or incomplete parts are excluded from recommendations and cannot be listed; bought parts arrive `unverified`; the copilot has a deterministic safety guard (mains power, smoke, swollen batteries) that runs before any model call and falls back to reading the current step if the service is down.

Demo accounts: `demo@secondlife.ai / demo1234`, seller `seller@secondlife.ai / seller1234`.


## v0.4 additions (dashboard, global copilot, listing assistant)

| Area | Endpoint |
|---|---|
| Dashboard numbers (platform + you, weekly series, categories, activity) | `GET /stats/impact` |
| Prefilled "sell this part" form (eligibility, title, qty, starting price) | `GET /marketplace/suggest/{item_id}` |
| Create listing (optional friendlier `title`) | `POST /marketplace/listings` |
| Copilot anywhere in the app: text and/or one photo, build context optional | `POST /copilot/chat` (multipart: `message`, `history` JSON string, `use_build`, `image`) |
| Device salvage proposals (never saved automatically) | `POST /teardown` |
| Inventory-backed resistor suggestions and LED resistor calculator | `GET /substitutions/resistor`, `GET /substitutions/led-resistor` |
| Guided component measurement and confirmation | `GET /testing/procedure/{category}`, `POST /testing/{item_id}/complete` |
| Current build photo review | `POST /builds/{build_id}/check-photo` |

These features are also available from the signed-in **Tools and testing** screen. Salvage assessments remain proposals until each part is confirmed through the inventory form; measurement results require explicit user confirmation. The teardown safety block runs before the existing Meta API client is called, and Tamil/Hindi safety keywords are included in both copilot endpoints.

New files: `services/impact.py`, `services/pricing.py`, `routers/stats.py`, `seed_community.py`.
No database schema changes (existing tables work as they are).

Dashboard maths (all disclosed in the UI under "How these numbers are worked out"):
- reused = parts required by builds marked finished; resold = parts in completed marketplace orders
- the headline e-waste figure is a lower bound (per category, the larger of reused/resold) because a part can be sold and then reused; the upper bound is shown next to it
- masses per part in `services/impact.py` are rough typical values, not measurements

Demo data: `python -m app.seed --demo && python -m app.seed_community` adds 14 invented makers with 12 weeks of builds and sales so the dashboard is not empty.
These rows are DEMO DATA; the dashboard shows an "Includes demo accounts" tag for any `@secondlife.ai` account. Say so in your submission.

Tests: `pytest` (new: `test_impact.py`, `test_pricing.py`, additions to `test_copilot.py`).

## v0.5: cart and checkout
| Endpoint | Purpose |
|---|---|
| `POST /checkout/preview` | prices a cart from the CURRENT listings (availability, own-listing and sold-out checks, delivery fee) |
| `POST /checkout/pay` | payment: address + payment method name + idempotency key; creates orders, adds parts to the buyer's inventory (unverified) and saves a receipt |
| `GET /checkout/payments` | the user's receipts |

- New table `payments` (created automatically; no existing table is altered). No card or UPI details are sent or stored: only the method name.
- Delivery fee (₹40, free from ₹300) is a made-up demo value in `services/checkout.py`.
- A retry with the same `idempotency_key` returns the same receipt, so a double click or network retry never pays twice.
- `simulate_decline: true` returns HTTP 402 and changes nothing (demo of a failed payment).
- The old one-click `POST /marketplace/listings/{id}/buy` still exists for the API but the app no longer uses it.
- Tests: `tests/test_checkout.py`.
