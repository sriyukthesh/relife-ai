# SecondLife AI frontend (React + TypeScript + Tailwind + Vite)

    cd frontend
    cp .env.example .env        # VITE_API_URL=http://localhost:8000
    npm install
    npm run dev                 # http://localhost:5173
    npm run build               # runs the TypeScript check, then bundles

Backend must be running (`uvicorn app.main:app --reload`) with CORS_ORIGINS including http://localhost:5173.
Demo login: demo@secondlife.ai / demo1234 (seller: seller@secondlife.ai / seller1234).

Screens: Scan (upload/camera -> part proposals with boxes -> confirm/correct each) · My parts · Data tables
(editable inventory, marketplace listings, and order history with filtering and CSV export) · Project timeline
(inventory-based planning, recovery, Bryntum Gantt and Scheduler) · Build with what I have
(ranked projects, missing parts, marketplace offers) · Guided build (steps read aloud, copilot Q&A) · Marketplace.

Notes
- Voice output uses the browser's speech synthesis. Voice input uses the browser's built-in speech recognition
  (Chrome/Edge/Safari), NOT Muse Voice Transcribe; that needs the official docs and a backend adapter.
- Camera: on phones the file picker opens the camera. Use HTTPS or localhost.
- The scan screen is the human-confirmation step: nothing reaches inventory until "Confirm & add".


## v0.4 changes
- New app shell: left rail on desktop, bottom tabs on phones, **Copilot button visible on every screen after login**.
- **Dashboard** is the landing page: parts kept in the loop, reused / resold / e-waste estimate, weekly chart, categories, your impact, activity, and a "how these numbers are worked out" disclosure.
- **Scan**: live camera (getUserMedia) with lighting hints, automatic identification on capture or upload, then a one-step **Sell on marketplace** assistant (prefilled name, quantity and starting price).
- **Copilot** (works with or without a build): type, speak, attach or capture a photo; "Start voice chat" is a hands-free loop (listen, answer, speak, listen).
- Marketplace "Sell a part" now uses the same listing assistant.

Notes
- Live camera needs **https or localhost**. To test on a phone, serve over https (e.g. an https tunnel) or use "Upload photo", which opens the phone camera.
- Voice input is the browser's SpeechRecognition (Chrome/Edge; audio is processed by the browser vendor's service), not Muse Voice Transcribe. Voice output is browser speech synthesis.
- Photo input to Copilot goes to Muse Spark through `POST /copilot/chat`; the model is told it cannot certify parts.

## v0.5: cart and checkout
Marketplace and "missing parts" use **Add to cart**. The Cart page is a four-step checkout: Cart, Delivery address, PayPal sandbox, and Review. PayPal handles payment details; on a verified sandbox capture, the parts appear in My parts as untested and a receipt is saved under "Your orders". Sandbox payments do not move live money.

Configure `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` and `PAYPAL_CURRENCY` in the backend environment using PayPal sandbox app credentials. The app prices in cents and uses a USD sandbox account; the client secret stays on the backend, and the frontend receives only the public client ID.

## Project timeline (Bryntum trial)

The signed-in **Project timeline** screen plans from that user's confirmed, usable inventory and stores its plan per account. It includes project recombination, delay/failure recovery, resource optimization, a Bryntum Gantt, and a Bryntum Scheduler.

Build the bundled Bryntum UI when deploying the backend:

```powershell
cd bryntum-ui
npm install
npm run setup:bryntum
npm run build
```

The build is written to `backend/sl_ui/timeline` and served by FastAPI at `/timeline-ui/`. The project-level `vite.config.ts` proxies this route and the timeline API to the backend for local development. Bryntum uses its trial packages; use a valid Bryntum license for production use if required by your plan.

External supplier prices may use Channel3; without that integration the UI identifies its built-in sample pricing as cached demo data. Supplier delivery times are simulated. Supplier purchases are **not** added to ReLife's PayPal checkout: open the supplier link, complete the purchase there, then explicitly mark it ordered to start its simulated delivery clock. PayPal remains reserved for ReLife marketplace listings.
