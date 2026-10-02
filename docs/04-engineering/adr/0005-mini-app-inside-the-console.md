# 0005: Mini-app inside the console

| | |
|---|---|
| Status | Accepted · amended in v3 (2 Oct 2026): placement, screens, UI stack, language |
| Owner | Omkar Kadam |
| Date | 2026-10-02 |
| Related | [PRD, N1](../../02-product/prd.md) · [fs-04 merchant mini-app](../../02-product/feature-specs/fs-04-merchant-mini-app.md) · [fs-07 cover purchase and consent](../../02-product/feature-specs/fs-07-cover-purchase-and-consent.md) · [Screens and flows](../../03-design/screens-and-flows.md) · [Design system](../../03-design/design-system.md) · [Data model and API](../data-model-and-api.md) · [Implementation guide](../implementation-guide.md) · [ADR 0004](0004-live-simulated-fallback-labels.md) · [ADR 0007](0007-hospital-cash-framing.md) |

## TL;DR

- A phone-sized merchant app, **"Chhatri in Paytm for Business"**, lives inside our own console. It is a third column beside the WhatsApp simulator on the merchant page, and a standalone full-screen route for phones and the static demo (N7). It is a prototype surface in our console, not an integration with the Paytm app.
- It is one React app with the console. It is not an iframe, not a separate PWA and not WhatsApp-only. Its code is `frontend/src/miniapp/`.
- Nine screens in three tabs (Home, Claims, Help). The consent centre adds two screens in wave 3.
- Its UI uses **Tailwind CSS v4 and shadcn/ui, scoped to the mini-app** under a `.miniapp` class. The console keeps its plain CSS tokens.
- It reads the same API as the console. It never calls Gemini, Sarvam, WhatsApp or Paytm itself; the backend does. Where an endpoint needs the officer token, the demo borrows the console's session.
- Everything is P0 (team decision, 2 Oct) and is built in waves behind feature flags. A screen that is not finished is hidden, never shown half-working.
- v3 corrects v2: the placement and widths, the screen list, the file location, the style description, and the claim that planned endpoints already exist.

## Context

**Track example.** Track 2 asks for insurance, lending and fintech that are simpler, faster and more human. Its example is the health insurance claims journey: understand coverage, submit documents, track claims, resolve queries. [ADR 0007](0007-hospital-cash-framing.md) explains how the hospital-cash claim fits it. The merchant surface is where that journey becomes visible.

**Constraint.** The final is on 3 Oct 2026: build on site, then demo. The demo runs live on the demo laptop, with the console full screen at 1280×720 and 100% zoom ([demo runbook](../../06-delivery/demo-runbook.md), [DEMO.md](../../DEMO.md)). The length of the demo slot is not announced. A second deployed app, a second device or a QR code is one more thing that can fail on the day.

**What existed at commit 86575ea (the starting point).**

- The merchant page, `frontend/src/pages/Merchant.tsx`: the WhatsApp phone simulator in a 372 px column, and a merchant panel (Soundbox device, money card, "What happened", merchant file, presenter notes).
- A live-state provider with an SSE stream and a replay clock, and an in-browser mock backend (`npm run dev:mock`, `?mock=1`) that makes a static demo possible.
- Plain CSS design tokens in `frontend/src/styles/tokens.css`: navy, blue and a light paper background, with Ubuntu and Noto Sans Devanagari self-hosted in `frontend/public/fonts/` (Noto covers Marathi).
- Endpoints the mini-app can use are listed under Decision 5.

**Status at the end of the build (3 Oct 2026):** BUILT. The mini-app (`frontend/src/miniapp/`), the scoped Tailwind and shadcn setup, the 14 feature flags and every endpoint in Decision 5 are in the code. The static build, the standalone route and the mock parity are BUILT too. Not done: the Marathi native review, and a deployed public URL for the static build.

**Opportunity.** The console is React already. A mini-app inside it gives judges one browser window, and gives the team one API, one mock backend, one clock and one session.

## Decision

### 1. Placement

At 1200 px and wider the merchant page has three columns: the WhatsApp phone (372 px), the mini-app frame (372 px, reusing the `.phone` bezel) and the merchant panel as one column of cards. From 900 to 1199 px the page has two columns (phone and frame) with the panel below. Below 900 px it has one column. 1200 px is the design width; narrower layouts degrade as stated rather than being refused. The frame has an "Open full screen" link to the standalone route.

The standalone route is `/merchant/:id/app`: full viewport, centred and at most 430 px wide on a desktop. It is a second route tree in `frontend/src/App.tsx`, inside `LiveProvider` and outside `AppShell`. It replaces the overlay modes of earlier drafts. Console changes are limited to this route glue, the merchant page layout and its container width (the `.merchant-page` grid in `frontend/src/styles/phone.css` stops at 1180 px today; it allows 1280 px with the third column).

### 2. One React app, no iframe

`frontend/src/miniapp/` holds the screens, the generated UI primitives (`ui/`), helpers and copy. The merchant page renders the frame and the standalone route renders the same root. Both share the API client, the SSE stream, the replay clock and the mock backend. The console imports from that folder for the route and page glue, and for nothing else.

### 3. Screens and navigation

Nine screens in three tabs. [fs-04](../../02-product/feature-specs/fs-04-merchant-mini-app.md) specifies each screen, its data and its states.

| Tab | Screens |
|---|---|
| Home | S1 Home, S2 Coverage explainer, S3 Cover and buy |
| Claims | S4 Claims, S5 Claim detail (the tracker), S6 Why this amount, S7 Trust receipt |
| Help | S8 Help, S9 Language |

The consent centre ([fs-07](../../02-product/feature-specs/fs-07-cover-purchase-and-consent.md)) adds S10 Consent centre and S11 Consent activity under Help in wave 3. Navigation is URL state (`screen`, `claim`, `decision`, `lang`, `mock`, `presenter`), so a deep link and the browser back button work without a nested router.

### 4. UI stack: Tailwind v4 and shadcn/ui, scoped to the mini-app

Team decision, 2 Oct. fs-04 section 5 holds the CSS entry file, the alias table and the collision list. The rules:

1. The console gets no Tailwind and keeps `frontend/src/styles/tokens.css`.
2. **No global reset.** Import the theme and utilities layers and nothing else. Never `@import "tailwindcss"`, which includes Preflight.
3. **Class detection is limited to the mini-app folder** (`source(none)` plus an explicit `@source`).
4. **Theme mapped to existing CSS variables.** `--mini-*` aliases are declared under `.miniapp`, each pointing at a console token. Tailwind's default palette is cleared.
5. **shadcn base styles are scoped under `.miniapp`.** Nothing is declared on `:root`, `body` or `*`. Radix portals mount inside `.miniapp`, and the frame is the containing block, so a Sheet or Toast never escapes it.
6. Console CSS is unlayered, so utilities carry the `important` flag, and a small mini-preflight (every selector prefixed `.miniapp`) resets what the console sets on bare elements.
7. 21st.dev components are added with `npx shadcn@latest add "https://21st.dev/r/<author>/<component>"` and land in `frontend/src/miniapp/ui/`.
8. **Vite 8.** The frontend runs Vite 8. On 2 Oct 2026 `@tailwindcss/vite` 4.3.3 lists `vite ^5.2.0 || ^6 || ^7 || ^8` as its peer range, so it is used. **If a later release drops Vite 8, use `@tailwindcss/postcss` instead**, with the same CSS entry.

A scratch build on 2 Oct 2026 with Vite 8.3 produced CSS with no Preflight rules, no utility used outside the mini-app folder, and `!important` on every utility. Unit tests do not process Tailwind, so isolation is tested on the built CSS and in the browser (fs-04 section 19).

### 5. Data and mocks

The mini-app calls the same API as the console, through the same client and envelope. It never calls Gemini, Sarvam, WhatsApp or Paytm itself. The backend calls them, and the app shows their LIVE, SIMULATED or FALLBACK state ([ADR 0004](0004-live-simulated-fallback-labels.md)).

| Status | Endpoints |
|---|---|
| BUILT | `GET /api/merchants/{id}`, `GET /api/decisions/{decision_id}`, `POST /api/premium/link` (officer token), `POST /api/webhooks/paytm`, `POST /api/merchants/{id}/messages`, `GET /api/policy`, `GET /api/integrations`, `GET /api/audit/verify`, and `GET /api/state` with `GET /api/stream` (the replay clock and refresh events that the console's `LiveProvider` already reads) |
| BUILT, wave 1 | `GET /api/merchants/{id}/cover`, `GET /api/merchants/{id}/claims`, `GET /api/decisions/{decision_id}/receipt` |
| BUILT, wave 2 | `POST /api/merchants/{id}/ask`, `POST /api/voice/stt`, `POST /api/voice/tts`, `POST /api/merchants/{id}/slip-precheck` and its `confirm`, `POST /api/integrations/{component}/fallback` |
| BUILT, wave 3 | `GET` and `POST /api/merchants/{id}/grievances`, `GET /api/merchants/{id}/consents`, `POST /api/merchants/{id}/consents/{consent_id}/withdraw`, `GET /api/merchants/{id}/consents/activity`, `POST /api/merchants/{id}/slips/{slip_id}/forget` |

Each endpoint is mocked in `frontend/src/mock` with the same view models, so its screen works, so the static demo (N7) works without a backend. The demo has no merchant login: `POST /api/premium/link` needs the officer token, and the standalone route borrows the console's demo officer session. A pilot would use the merchant's own Paytm login.

### 6. Language

The mini-app keeps its own language state, separate from the console. The order is the URL `lang`, then a stored preference, then the merchant's `language` field, then Hindi. Hindi and English are complete. Marathi follows native review (wave 4, flag `n8_marathi`), and each string falls back from Marathi to Hindi to English. The WhatsApp phone keeps showing Hindi and English on every message, and the console UI stays English. This settles the language question left open in v2.

### 7. Waves and flags

Everything is P0 and is built in waves behind flags. The flags are `n1_miniapp`, `n2_ask_chhatri`, `n3_slip_precheck`, `n4_voice`, `n5_grievances`, `n6_consents` and `n8_marathi`, among the 14 in `backend/chhatri/features.py` and `frontend/src/features.ts`; the [implementation guide](../implementation-guide.md) owns the mechanism. Off means absent from the UI: no empty shell and no "coming soon".

| Wave | What ships for the mini-app |
|---|---|
| 0 setup | Flags; the scoped Tailwind and shadcn setup; the frame and route skeleton behind `n1_miniapp` |
| 1 demo spine | S1 to S9 in Hindi and English, tracker, trust receipt, jargon lens, next-best-action bar, the three wave 1 endpoints, mock parity |
| 2 live AI | Help rows for Ask Chhatri, slip pre-check and voice |
| 3 trust and rights | Help rows for grievances and consents (S10 and S11), the dispute button moves from the chat path to the grievance endpoint, the consent block on S3 |
| 4 judge wow | Marathi |
| 5 ship | Static build with the standalone route, deep-link fallback, rehearsals |

### 8. Honesty rules

Every status says BUILT or not built. Sales, alerts, KYC, payouts, the lender, Soundbox, WhatsApp and the Paytm link are SIMULATED and labelled as such in the app. The N1 screens show no AI-written text. The policy engine decides every amount; the app renders the numbers it is given and never computes them. The accessibility target is WCAG 2.2 AA, checked with the `jsx-a11y` lint rules and a manual keyboard pass.

## Alternatives considered

1. **Separate PWA deployed to a free host** (rejected). Pro: looks production-like. Con: it needs internet, adds a domain, judges may not find the link, a failed deploy stalls the demo, and it does not fit a demo that runs live on one laptop. The static demo (N7) can still be hosted by the repo owner, but it is this same app built statically.

2. **WhatsApp-only merchant experience** (rejected). Pro: simpler code. Con: the track example needs a visible tracker and a receipt, which a chat window cannot hold, and the WhatsApp surface is SIMULATED in this prototype.

3. **QR code to a local server on the demo laptop** (rejected). Pro: two separate devices. Con: the demo Wi-Fi becomes a single point of failure, judges cannot see the app and the console in one view, and it needs a second screen.

4. **An iframe holding a separate mini-app** (rejected). Pro: hard style isolation. Con: a second build and entry point, a second session and clock, duplicate mock and SSE wiring, and message passing for deep links and language. Scoped CSS gives enough isolation, and we test it.

5. **Console CSS alone, no new stack** (rejected). Pro: no new dependency and nothing to isolate. Con: a day of hand-writing accessible sheets, tabs, switches, accordions and toasts, and 21st.dev and shadcn components could not be used as they are written for Tailwind.

6. **Tailwind globally, with a console migration** (rejected). Pro: one system. Con: Preflight and utility collisions would change console pages that have a passing test suite and a projector-ready look, for no gain a judge would see.

## Consequences

**Positive:**

- **Single-window demo:** judges follow the merchant app, the WhatsApp phone and the officer console in one browser window, one route change apart.
- **Reuse:** one API client, one mock backend, one stream, one clock and one session serve every surface.
- **Resilience:** no extra server or deploy. If the console works, the mini-app works.
- **Consistency:** the mini-app reads the console's tokens through aliases, and shares the Devanagari fonts.
- **The track journey becomes visible as the waves ship:** understand coverage (S2), submit documents (slip pre-check, wave 2), track claims (S4 and S5), resolve queries (dispute in wave 1, grievance ladder in wave 3).
- **Isolation is checkable:** a build-output check and a computed-style test, not a promise.

**Negative:**

- **Screen real estate:** three columns at 1280 px are tight. The merchant panel is one column of cards, the page drops to two columns below 1200 px, and the standalone route gives a full screen.
- **Two styling systems in one repository:** a new dependency set (Tailwind, Radix, generated shadcn files) and rules contributors must follow, such as no bare console class names in mini-app markup.
- **Generated files need care:** each shadcn `add` needs a diff review, and the generated files need a one-time edit for the portal container and 44 px targets.
- **Bundle size grows.** Measure it with `vite build` in wave 0 and split the mini-app chunk if the console load suffers. No size is claimed here.

**Risks:**

- **API mock mismatch:** the app calls an endpoint the mock lacks. Mitigation: a mock route and a contract test per endpoint before its screen turns on (fs-04 section 6.4).
- **Style leakage in either direction.** Mitigation: the build-output check and the Playwright computed-style test (fs-04 section 19).
- **A planned endpoint is late.** Mitigation: its screen stays behind its flag.
- **The borrowed officer session.** It is acceptable for the demo, not for a pilot; the static mock build needs none.
- **Zoom and resize.** A zoomed-in browser narrows the viewport in CSS pixels, so the page falls back to two columns. Mitigation: test at 1280×720 and at a phone width.

## How we will know it was right

These are targets for the build, not results. The acceptance criteria are in [fs-04](../../02-product/feature-specs/fs-04-merchant-mini-app.md) section 17.

1. Screens S1 to S9 pass AC-07 to AC-41 in the console at 1280×720 and on the standalone route at 390×844.
2. The merchant page shows the phone, the mini-app frame and the merchant panel in one browser window (AC-01), and the standalone route fills a phone viewport with no console header (AC-03).
3. Against a running backend, the tracker and the receipt for Anil show the decision and the ₹1,380 that the officer console shows (AC-17 and AC-27 on the live project).
4. The mini-app follows the console's replay clock: seeking back removes a paid claim from Home (AC-41).
5. In the mock project, Ramesh's price check ends BLOCKED with the right start date and price (AC-13), and Anil's claim reaches its receipt (AC-17, AC-27). The end-to-end specs are `miniapp-buy-blocked`, `miniapp-area-claim` and `miniapp-receipt-print`.
6. The console is unchanged: its unit tests pass (see the testing strategy for the measured count), computed styles of console elements are equal with and without the mini-app chunk (AC-05), and the built CSS holds no Preflight rule outside `.miniapp` (AC-06).

## Follow-ups

Owners: Omkar Kadam (frontend), Ujjwal Pardeshi (backend).

- **Wave 0 (Omkar):** feature flags; the scoped Tailwind and shadcn setup (CSS entry, alias table, mini-preflight, `@/` alias, `components.json`); the frame and route skeleton behind `n1_miniapp`; the build-output check.
- **Wave 1:** S1 to S9 with Hindi and English (Omkar); the `cover`, `claims` and `receipt` endpoints (Ujjwal); mock parity and the end-to-end specs for buy, claim and dispute in the mock project (Omkar).
- **Wave 2:** Help rows for Ask Chhatri, slip pre-check and voice (Omkar).
- **Wave 3:** grievance and consent screens (Omkar) and their endpoints (Ujjwal).
- **Wave 4:** Marathi after native review (Omkar).
- **Wave 5:** the static build with the standalone route and a deep-link fallback; rehearsals (Omkar).
- **Any wave:** the implementation guide records the boundary between console code and mini-app code.

## Open questions

1. **Public URL (N7).** The repo owner deploys the static build to a free host, and deep links need a single-page fallback there. No URL exists yet and none is claimed. Owner: Omkar Kadam.
2. **Merchant session.** Should the live demo or a pilot add a merchant-scoped quote endpoint instead of borrowing the officer session? Owner: Ujjwal Pardeshi.
3. **Flag mechanism and names.** Settled: the 14 names in `features.ts` and `features.py`, kept identical by `scripts/tests/test_feature_flags.py`.
4. **Native review.** Who reviews the Hindi copy, and later the Marathi? Owner: Omkar Kadam.

## Changelog

- 2026-10-03 · v3.1 · status synced with the code at the end of the build: BUILT, flags named, the stale test count and the PLANNED wording removed.
- 2026-10-02 · v3 · amended. Resolved the contradictions between six listed screens, a five-tab bar and "five screens" in the signals: nine screens in three tabs, plus two consent screens in wave 3. Stated the placement exactly (third column at 1200 px and wider, two columns from 900 px, one below, a 372 px frame, plus the standalone route `/merchant/:id/app`) and dropped the 375 px overlay modes. Moved the code to `frontend/src/miniapp/` from `pages/MerchantApp.tsx`. Said that the app calls our API and nothing else (Gemini, Sarvam, WhatsApp and Paytm are backend integrations) and marked the endpoints that do not exist yet as PLANNED. Corrected the style description (the console uses navy and blue tokens, not green and white). Added the UI stack decision (Tailwind v4 and shadcn/ui, scoped, with the Vite 8 note), language as the mini-app's own state, waves and flags, and the alternatives iframe, console CSS alone and Tailwind globally. Replaced the past-tense "tested on 2 Oct" signal with targets.
- 2026-10-02 · v2 · consistency check against the code: no changes needed; ADR correctly scopes mini-app as a PLANNED component (N1) for 2–3 Oct build.
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned: verified ADR 0005 correctly scopes mini-app APIs and mocking; no changes needed (compliant with canonical framing).
- 2026-10-02 · v1 · first draft.
