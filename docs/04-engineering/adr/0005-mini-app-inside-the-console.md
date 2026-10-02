# 0005: Mini-app inside the console

| | |
|---|---|
| Status | Accepted |
| Owner | Omkar Kadam |
| Date | 2026-10-02 |
| Related | [PRD, N1](../../02-product/prd.md) · [Feature spec fs-04](../../02-product/feature-specs/fs-04-merchant-mini-app.md) · [Screens and flows](../../03-design/screens-and-flows.md) |

## TL;DR

A phone-sized merchant mini-app, **"Chhatri in Paytm for Business,"** is built as a React component inside the console, side by side with the WhatsApp phone simulator. It is not a separate PWA or a WhatsApp-only experience. This keeps the demo in one browser tab, makes it easy for judges to see both the merchant and officer surfaces simultaneously, and reuses the same API mocks. It is the track's primary merchant journey (track example: health claims).

## Context

**Track requirement:** "simplify the health insurance claims journey." The example flow is: understand coverage → submit documents → track claims → resolve queries. The merchant surface is essential to demonstrate this journey.

**Constraint:** one demo laptop, one browser. Building a separate PWA or deploying to a staging server adds complexity and a single point of failure. Deploying on the same laptop with a local server is fragile (port conflicts, browser security).

**Opportunity:** React (which the console already uses) can render a phone-sized iframe or component. A mini-app inside the console means:

- Judges see merchant and officer surfaces side by side in a single browser window.
- The same backend mock API serves both.
- Styling is consistent (both use the design tokens, Devanagari).
- Navigation is simple (no new domain, no QR code needed).

## Decision

The mini-app is a **React component** at `frontend/src/pages/MerchantApp.tsx`. It is rendered inside the console at a phone-sized viewport (375 px wide, full height) in a side panel or an overlay. The component uses the same API client and integrations (Gemini, Sarvam, WhatsApp, Paytm) as the rest of the console.

**Screens** (N1):

1. **Home and cover card:** merchant name, current zone, cover status (active, waiting period, expired), premium paid until, annual limit used.
2. **Coverage explainer:** "What am I covered for?" Examples (area income loss, hospital cash), caps, exclusions, waiting period, alert look-ahead.
3. **Consent and buy:** consent form (sales data for cover, slip data for claims), simulated Paytm payment link (SIMULATED badge), cash-before-cover explanation.
4. **Claim tracker:** steps (Detected → Checked → Decided → Paid → EDI holiday), each with a plain reason, decision id, expected timing (e.g., "Checked at 17:04").
5. **Help and grievance:** Ask Chhatri (grounded LLM), dispute button (opens a case, SLA clock shown), escalation ladder (GRO → Bima Bharosa → Ombudsman).
6. **Receipt and audit:** payout receipt (decision id, formula, sources, audit hash prefix), printable to PDF.

**Navigation:** a bottom tab bar switches between Home, Coverage, Consent, Tracker, Help.

**APIs:** the mini-app calls the same endpoints as the officer console:

- GET /api/merchants/{id}/cover (cover status and premium)
- GET /api/merchants/{id}/claims (tracker items)
- POST /api/merchants/{id}/ask (Ask Chhatri)
- GET /api/decisions/{id} (payout explanation)
- GET /api/decisions/{id}/receipt (receipt)
- POST /api/merchants/{id}/grievances (open a dispute)

**Default merchant:** the demo uses Anil Jadhav (S-0142, zone Z7) as the logged-in merchant. Switching merchants (e.g., to Ramesh S-0907) is a URL param or a test harness option.

**Styling:** Hindi-first with an English toggle (language button top right). Devanagari fonts (Noto Sans Devanagari), green-and-white tokens (matching the console), accessibility (WCAG AA, semantic HTML).

## Alternatives considered

1. **Separate PWA deployed to Vercel** (rejected): A standalone app deployed to a free Vercel URL. Pro: looks production-like. Con: requires internet; one more domain; judges may not find the link; a deploy failure stalls the demo; not aligned with "same laptop, one browser."

2. **WhatsApp-only merchant experience** (rejected): All merchant actions (buy, check status, dispute) happen via WhatsApp conversation. Pro: simpler code. Con: the track example is "health claims journey end to end," which needs a visual tracker, not just chat; WhatsApp is SIMULATED (no test phone verified), so it does not demonstrate the actual surface.

3. **QR code to a local server on the demo laptop** (rejected): Mini-app served on `localhost:5173`, QR code scanned on the officer's phone during the demo. Pro: two separate devices. Con: single point of failure (demo WiFi); judges cannot see both surfaces at once; needs a second screen.

## Consequences

**Positive:**

- **Single-window demo:** judges see merchant and officer journeys side by side without context switching.
- **Reuse:** the same API mocks and backend serve both surfaces, reducing code and test burden.
- **Resilience:** no external servers or deploys; if the console is working, the mini-app works.
- **Consistency:** design tokens, language toggles, Devanagari are shared; no duplication.
- **Transparent journey:** the track example (health claims) is fully demonstrated end to end: merchant understands cover, buys, submits a slip, sees tracking, escalates a dispute.

**Negative:**

- **Screen real estate:** the console is already information-dense (hex map, officer queue, audit). Side-by-side display is cramped on a 13" laptop screen. Mitigate: overlay mode (click a button to show the mini-app fullscreen, then back to the console) or a third monitor if available.
- **Navigation complexity:** switching between officer and merchant modes requires clear UX (tabs, buttons). If buttons are small, judges may miss the merchant surface.

**Risks:**

- **API mock mismatch:** if the mini-app calls an endpoint that the mock backend does not have, the demo fails. Mitigate: mock all the endpoints listed above (N1) before final rehearsal.
- **Responsive design breaks:** if the viewport is resized (e.g., browser zoom), the mini-app may not fit. Mitigate: use CSS media queries and test zoom levels.
- **Language toggle state:** if the merchant app is in Marathi (N8) but the console is in English, the experience is jarring. Mitigate: share language state (React context) between the two.

## How we will know it was right

**Signals:**

1. All five mini-app screens render without errors on the demo laptop (tested on 2 Oct).
2. Judges can see both merchant and officer surfaces in one browser window during the demo.
3. The merchant tracker shows the same decision id and payout as the officer console (data consistency test).
4. The mini-app responds to the same scenario seed as the console (determinism test).
5. Merchant can buy cover, see the cover card updated, then see the claim in the tracker (end-to-end journey test, track example).

## Follow-ups

- **Task:** Build all five mini-app screens (N1) by end of day 2 Oct; Omkar leads.
- **Task:** Mock the six API endpoints in the frontend mock server (npm run dev:mock); shared effort.
- **Task:** Test responsive design on the demo laptop (13" MacBook, iPad, etc.) and set a minimum width (e.g., 1200 px).
- **Task:** Write an e2e test for the merchant journey (buy → claim → dispute).

## Open questions

1. Should the mini-app be accessible on a public URL after the hackathon (N7), or is it demo-only? Owner: Omkar Kadam.
2. Is a language toggle per screen (mini-app and console separate) acceptable, or must both switch together? Owner: Omkar Kadam.

## Changelog

- 2026-10-02 · v2 · final consistency pass against the code: no changes needed; ADR correctly scopes mini-app as a PLANNED component (N1) for 2–3 Oct build.
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned: verified ADR 0005 correctly scopes mini-app APIs and mocking; no changes needed (compliant with canonical framing).
- 2026-10-02 · v1 · first draft.
