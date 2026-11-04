# SecondLife AI frontend (React + TypeScript + Tailwind + Vite)

    cd frontend
    cp .env.example .env        # VITE_API_URL=http://localhost:8000
    npm install
    npm run dev                 # http://localhost:5173
    npm run build               # runs the TypeScript check, then bundles

Backend must be running (`uvicorn app.main:app --reload`) with CORS_ORIGINS including http://localhost:5173.
Demo login: demo@secondlife.ai / demo1234 (seller: seller@secondlife.ai / seller1234).

Screens: Scan (upload/camera -> part proposals with boxes -> confirm/correct each) · My parts · Build with what I have
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
Marketplace and "missing parts" now use **Add to cart**. The Cart page (button with item badge, top bar on phones and left rail on desktop) is a 4-step checkout: Cart, Delivery address, Payment method (UPI, demo card, net banking), Review and **Pay ₹X**. On success the parts appear in My parts as untested and a receipt is saved under "Your orders". It is a simulation: no real money, and the UI tells users never to type real card or UPI PIN details.
