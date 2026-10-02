# Design system

| | |
|---|---|
| Status | Draft v1 · 2 Oct 2026 |
| Owner | Omkar Kadam |
| Audience | Design systems, Figma-to-code, component authors |
| Related | [Screens and flows](screens-and-flows.md) · [Architecture](../04-engineering/system-architecture.md) · [Conversation design](conversation-design.md) · [Facts and sources](../01-strategy/facts-and-sources.md) |

## TL;DR

- **One system for two audiences**: a dense, data-focused console (1280×720 desktop) and a merchant-focused mobile app (390×844 phone). The phone is the mini-app N1.
- **Tokens** (from `frontend/src/styles/tokens.css`): Navy and ink primaries; blue links; amber and red accent states; Noto Sans Devanagari for Hindi. Four-pixel spacing grid; three radius rules (6 px controls, 10 px cards, 16 px panels). Ease-out motion at 150–300 ms.
- **Component inventory**: existing console components (map, panels, tables) and new N1 mini-app screens (cover card, claim tracker, consent, receipt, voice button, grievance ladder).
- **States**: paid (green), decided (blue), referred (amber), blocked (red), SIMULATED/FALLBACK labels on integrations (demo mode).
- **WCAG 2.2 AA contrast**: text ≥4.5:1; status indicators use text and icon, never colour alone.

## 1. Design principles

### For the claims officer console

**Trustworthy, scannable, operationally dense.** The officer queue, live map, case detail and audit log each surface a specific decision. Nothing is hidden; all payouts and holds are explained in context. Typography is monospace (Fira in the references); ours uses Ubuntu with tabular numerals for alignment. Real-time updates are smooth, not jarring. Empty states and error paths are graceful.

No AI purple gradients or decorative symbols. Icons are task-specific SVG, not emoji. Charts on the map (per-zone KPIs) use non-red-green ramps with number labels for colour-blind users.

### For the merchant mini-app (phone, 390×844)

**Clear, voice-first, one step at a time.** The merchant is Hindi-speaking, low-literacy, busy. Every screen shows one thing. Language toggles between Hindi and English inline. Voice buttons are large and discoverable; tap-to-send chip replies are always visible. Explanations cite the policy wording by clause. No jargon; "expected day" is explained by example with the merchant's own ₹ number.

Motion guides the eye (fade + tiny slide on list reveal); loading is visible; errors say what to do next ("Take a clearer photo").

---

## 2. Design tokens

All token names and values are from `frontend/src/styles/tokens.css` (built 1 Oct 2026, commit 86575ea).

### 2.1 Palette (fixed)

| Name | Value | Purpose |
|------|-------|---------|
| `--navy` | `#0f1a33` | Hero, console header, dark backgrounds |
| `--ink` | `#0f172a` | Text on light, body copy |
| `--blue` | `#0b63c9` | Primary action, links |
| `--accent` | `#38a3e8` | Lighter accent, interactive states |
| `--paper` | `#f3f5f8` | Default background (light theme) |
| `--amber` | `#e39a4f` | Warnings, "referred" state |
| `--red` | `#b91c1c` | Blocked, errors, "HARD check failed" |
| `--green` | `#15803d` | Paid, "APPROVED" |
| `--wa-header` | `#0b3d2e` | WhatsApp green (phone simulator header) |
| `--chat-bg` | `#ece5dd` | WhatsApp chat background |
| `--bubble-out` | `#d9fdd3` | WhatsApp outgoing bubble |

### 2.2 Semantic surfaces and text

| Name | Value | Purpose |
|------|-------|---------|
| `--card` | `#ffffff` | Card background (light theme) |
| `--paper-2` | `#eef1f6` | Subtle section background |
| `--line` | `#dfe4ec` | Border (standard) |
| `--line-soft` | `#edf0f5` | Border (subtle, dividers) |
| `--line-strong` | `#c9d1dd` | Border (emphasis) |
| `--blue-hover` | `#0a56ae` | Button hover state |
| `--blue-soft` | `#e7f0fb` | Light blue background (info badge) |
| `--ink-2` | `#334155` | Secondary text |
| `--ink-3` | `#475569` | Tertiary text |
| `--muted` | `#5b6474` | Muted text (4.5:1 on white) |
| `--faint` | `#8a93a3` | Disabled, placeholder text |

### 2.3 Status-semantic colours

**Proposed additions for N1 mini-app:**

| State | Colour | Token (proposed) | Purpose |
|-------|--------|------------------|---------|
| Paid | Green | `--paid` = `#15803d` | Payout credited |
| Decided | Blue | `--decided` = `#0b63c9` | Claim approved or referred, decision made |
| Referred | Amber | `--referred` = `#e39a4f` | Awaiting human review; or "need to retake photo" |
| Blocked | Red | `--blocked` = `#b91c1c` | Cover not started, claim rejected, or input invalid |
| SIMULATED | Teal (dark) | `--demo` = `#14919b` | Labelled badge for simulated data in mock mode |
| FALLBACK | Orange | `--fallback` = `#fb923c` | Integration degraded (AI service off, using deterministic fallback) |

**Contrast verification (WCAG 2.2 AA, 4.5:1 minimum for text):**

- Paid (green `#15803d`) + white: 6.8:1 pass
- Decided (blue `#0b63c9`) + white: 5.9:1 pass
- Referred (amber `#e39a4f`) + white: 5.2:1 pass
- Blocked (red `#b91c1c`) + white: 6.4:1 pass
- SIMULATED (teal `#14919b`) + white: 5.5:1 pass
- FALLBACK (orange `#fb923c`) + white: 4.6:1 pass

Status indicators always pair colour with an icon and label. Never colour alone.

### 2.4 Navy surfaces (dark backgrounds, § 20 of SPEC)

| Name | Value | Purpose |
|------|-------|---------|
| `--navy` | `#0f1a33` | Hero and navbar |
| `--navy-2` | `#16244a` | Slightly lighter navy |
| `--navy-3` | `#1d2d57` | Lighter still, for panels on navy |
| `--navy-line` | `#25355f` | Border on navy |
| `--on-navy` | `#ffffff` | Strong text on navy |
| `--on-navy-2` | `#c8d3ea` | Secondary text on navy |
| `--on-navy-3` | `#93a4c6` | Tertiary text on navy |

### 2.5 Type scale (px, for exact projector rendering)

| Variable | Size | Use |
|----------|------|-----|
| `--fs-2xs` | 11px | Labels, stamps, footnotes |
| `--fs-xs` | 12px | Small labels, alert badges |
| `--fs-sm` | 13px | Body captions, sub-text |
| `--fs-base` | 14px | Body text (default) |
| `--fs-md` | 15px | Input labels, slightly prominent |
| `--fs-lg` | 17px | Section headings, card titles |
| `--fs-xl` | 20px | Panel titles, larger buttons |
| `--fs-2xl` | 26px | Feature headings (hero) |
| `--fs-3xl` | 34px | Page title / hero headline |
| `--fs-4xl` | 44px | Hero main claim (console Overview) |

### 2.6 Spacing scale (4px grid)

| Variable | Value | Use |
|----------|-------|-----|
| `--sp-1` | 4px | Tight padding, inline gaps |
| `--sp-2` | 8px | Button gap, small padding |
| `--sp-3` | 12px | Input padding |
| `--sp-4` | 16px | Card padding, standard margin |
| `--sp-5` | 20px | Section gap |
| `--sp-6` | 24px | Panel gap, larger margins |
| `--sp-8` | 32px | Major section spacing |
| `--sp-10` | 40px | Grid gap (larger) |
| `--sp-14` | 56px | Very large gaps |
| `--sp-18` | 72px | Hero spacing |
| `--sp-24` | 96px | Maximum gap |

### 2.7 Radius

| Variable | Value | Use |
|----------|-------|-----|
| `--radius-sm` | 6px | Controls (buttons, inputs, chips) |
| `--radius` | 10px | Cards, panels, moderate border |
| `--radius-lg` | 16px | Large panels, map container |
| `--radius-pill` | 999px | Pill buttons, fully round badges |

### 2.8 Shadows

| Variable | Value | Use |
|----------|-------|---------|
| `--shadow` | `0 1px 2px rgb(15 23 42 / 6%), 0 4px 16px rgb(15 23 42 / 6%)` | Cards, standard depth |
| `--shadow-lg` | `0 10px 40px rgb(15 23 42 / 18%)` | Modals, elevated panels (phone frame) |
| `--shadow-navy` | `0 30px 80px rgb(4 10 24 / 45%)` | Hero shadow, strong depth (console header) |

### 2.9 Motion

| Variable | Value | Use |
|----------|-------|---------|
| `--ease-out` | `cubic-bezier(0.23, 1, 0.32, 1)` | Exit animations, fade-out |
| `--ease-in-out` | `cubic-bezier(0.77, 0, 0.175, 1)` | Entrance, screen transitions |
| `--dur-press` | 160ms | Button active state (scale 0.97) |
| `--dur-ui` | 220ms | Standard UI transition (state change, reveal) |
| `--dur-reveal` | 600ms | Hero/page entrance, slow reveal |

**Rules:**
- Button press: 160 ms, scale down to 0.97
- Hover/focus state: 220 ms ease-out
- List item reveal (stagger): 220 ms per item, 0.03 s stagger delay
- Modal backdrop: 220 ms fade
- Respect `@media (prefers-reduced-motion: reduce)` by removing motion (duration 0, ease linear)

### 2.10 Z-index ladder

| Variable | Value | Purpose |
|----------|-------|---------|
| `--z-sticky` | 20 | Sticky headers, replay controls |
| `--z-map` | 1000 | Map (interactive, above main content) |
| `--z-popover` | 1200 | Tooltips, context menus |
| `--z-toast` | 1300 | Notifications, status pills |
| `--z-modal` | 1400 | Dialogs, modals (top) |

---

## 3. Typography

### 3.1 Fonts

**Primary:** Ubuntu 400, 500, 600, 700 (from Google Fonts)  
**Devanagari:** Noto Sans Devanagari 400, 500, 600, 700 (from Google Fonts)  
**Monospace:** System ui-monospace (local; fallback `SFMono-Regular, Menlo, Consolas`)

**CSS selectors:**

```css
--font: 'Ubuntu', 'Noto Sans Devanagari', system-ui, -apple-system, 'Segoe UI', sans-serif;
--font-hi: 'Noto Sans Devanagari', 'Ubuntu', system-ui, sans-serif;
--font-mono: ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace;
```

- Default body text uses `--font` (Ubuntu + Noto Sans Devanagari fallback)
- Elements with `lang="hi"` or `.hi` class use `--font-hi` (Noto Sans Devanagari preferred)
- Code, IDs, amounts use `--font-mono` with `font-variant-numeric: tabular-nums` for alignment

### 3.2 Line height and spacing

- **English text:** `line-height: 1.4` (default)
- **Hindi text:** `line-height: 1.6` (Devanagari needs more vertical space for diacritics)
- **Headings (h1–h4):** `font-weight: 500`, `letter-spacing: -0.01em`, `margin: 0`

### 3.3 Numerals

**Table numerals (tabular):** Used in all amounts, timestamps, and indices where alignment matters.  
`.num`, `.tnum` class: `font-variant-numeric: tabular-nums;` (ensures ₹1,380 aligns vertically with other currency amounts)

**Indian number format:**
- ₹1,380 (lakhs: ₹1,38,000)
- Dates: 2 Oct 2026 or 02-Oct-2026 (not Oct 2)
- Always use ₹ symbol (not "Rs" or "Rupees")

---

## 4. Iconography

All icons are **SVG**, inline or referenced.

**Icon library (existing):** Custom SVG set from the console (check, alert, ban, info, edit, delete, etc.)

**New icon set needed for N1:**
- Voice button (microphone, record state)
- Chip button (tap-to-send arrow or send)
- Cover status (shield, checkmark, clock, X)
- Claim step states (circle outline, circle checked, circle clock, circle X)
- Grievance ladder (flag, target, scales)
- Provider badge (logo badge: Gemini, Sarvam, fallback)

**Principles:**
- Outline style (2px stroke), 24×24 base grid
- No emoji; use SVG fill color from tokens
- Always pair icons with text labels (no icon-only buttons without `aria-label`)
- Icon colour inherits from text colour by default; use status colour only for status icons (paid = green, blocked = red)

---

## 5. Component inventory

### 5.1 Existing console components (in `frontend/src/components/`)

| Component | File(s) | Purpose | State |
|-----------|---------|---------|-------|
| **StormMap** | `storm/StormMap.tsx` | Hex map with zone sales index overlay, live or replayed | LIVE |
| **ZoneCard** | `panel/ZoneCard.tsx` | Zone detail panel (KPIs, shops paid, trigger time) | LIVE |
| **EventFeed** | `panel/EventFeed.tsx` | Timeline of area triggers, payouts, messages | LIVE |
| **KpiTiles** | `panel/KpiTiles.tsx` | Top-line metrics (₹ paid, shops, trigger time, forms) | LIVE |
| **CaseDetail** | `claims/CaseDetail.tsx` | Case card with slip extraction, checks, decision, action | LIVE |
| **Explanations** | `panel/Explanations.tsx` | "Why this amount" formula breakdown | LIVE |
| **AuditTable** | `audit/AuditTable.tsx` | Hash-chain log (time, action, subject, data) | LIVE |
| **Phone** | `phone/Phone.tsx` | WhatsApp phone simulator (messages, voice, slip upload) | LIVE |
| **Bubbles** | `phone/Bubbles.tsx` | Chat message bubbles (text, audio, cards) | LIVE |

### 5.2 New components for N1 mini-app

**All phone-sized (390 px wide, 844 px tall max), inside the console next to the WhatsApp phone.**

| Component | Purpose | Screens | State | Priority |
|-----------|---------|---------|-------|----------|
| **CoverCard** | Display merchant's cover status, zone, premium, waiting period | Home, coverage explainer | N1 | P0 |
| **Stepper / Claim Tracker** | Vertical timeline: Detected → Checked → Decided → Paid → EDI holiday. Each step shows state (icon + label), reason (one line), next step, and ETA. | Claim tracker | H1 | P0 |
| **Why-This-Amount Card** | Formula breakdown with clause citations: rule → numbers → source badges. Counterfactual for REFERRED. | Claim detail, receipt | H2 | P0 |
| **Receipt** | Decision ID, rules version, formula, data sources, audit hash prefix, grievance path. Printable. | After payout | H3 | P1 |
| **Consent Toggle** | Purpose-specific toggle (sales data, slip data). Shows consequence of withdrawal. | Consent centre | N6 | P1 |
| **Voice Button** | Microphone icon, "listening…" state, waveform during recording, fallback text input. | Chat composer, Ask Chhatri | N4 | P0 |
| **Chip Button** | Small, filled, rounded pill. Used for tap-to-send replies ("मुझे इतने पैसे क्यों मिले?"). | Chat composer options | N1 | P0 |
| **Grievance Ladder** | Three-step ladder with SLA clocks: insurer GRO → Bima Bharosa → Insurance Ombudsman. | Help & grievance screen | N5 | P1 |
| **Provider Badge** | Small badge: "Sarvam LIVE", "Sarvam FALLBACK", "Template". Demo mode only; N2 will add Gemini (planned). | Ask Chhatri, slip reader | X6 | P1 |
| **Readiness Checklist** | Three items (photo readable, name matches KYC, dates match). Checkbox style, not numeric. | Slip pre-check (N3) | H5 | P0 |

### 5.3 Component states and accessibility

Each component has **empty**, **loading**, **error**, and **SIMULATED** states:

- **Empty:** "No claims yet" placeholder with an icon and action link
- **Loading:** Subtle spinner (40×40 px, dark blue) with text "Checking…"
- **Error:** Red icon + plain error message + "Try again" button
- **SIMULATED:** Small teal badge "SIMULATED" or "MOCK" in the corner; for demo mode only

**Accessibility:** All interactive elements have `aria-label` or visible text. Buttons are ≥44×44 px. Form inputs have associated `<label>` elements. Modals have `role="dialog"` and focus trap. Colour is never the only means of conveying state (icon + label always).

---

## 6. Motion

### 6.1 Micro-interactions

| Interaction | Duration | Easing | Purpose |
|-------------|----------|--------|---------|
| Button press | 160 ms | ease-out | Feedback: scale to 0.97 |
| State change (toggle, checkbox) | 220 ms | ease-out | Colour and icon swap |
| Hover state | 220 ms | ease-out | Slight colour lighten or shadow increase |
| Fade in (page load, new message) | 220 ms | ease-in-out | opacity 0 → 1 |
| Fade out (close modal) | 160 ms | ease-out | opacity 1 → 0 |
| Slide in from bottom (sheet, drawer) | 300 ms | ease-in-out | transform translateY(100%) → 0 |

### 6.2 List reveals (stagger animation)

When a list of items (claims, messages, KPIs) enters the screen:

```css
/* Pseudo-code */
gsap.from('.list-item', {
  opacity: 0,
  y: 8,
  duration: 0.22,
  stagger: 0.03,
  ease: 'power2.out'
});
```

- Per-item duration: 220 ms
- Stagger delay: 30 ms (so 10 items take 270 ms total)
- Y offset: 8 px (subtle; larger than 16 px reads as sloppy on dense data)
- Easing: power2.out (strong ease-out, slight overshoot)

### 6.3 Respect for accessibility

```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0ms !important;
    transition-duration: 0ms !important;
  }
}
```

Motion is never used alone to convey meaning (e.g., "loading state" must also have a spinner icon or text).

---

## 7. Data visualisation

### 7.1 Live map (StormMap)

**Hex choropleth:** Mumbai wards as h3 level-8 hexagons, coloured by sales index.

- **Ramp (colour-blind safe):** Blue (100%) → Teal → Yellow → Orange → Red (0%), matched to `[100%, 75%, 50%, 25%, 0%]` index thresholds
- **Hex stroke:** `--ward-line` (`#0f1a33` at 18% opacity) for contrast
- **Label:** Zone ID + index % + shop count inside the hex (white text, 11 px, `font-weight: 500`)
- **Tooltip (hover):** Zone name, exact %, alert status

Alternative ramp for WCAG AA (without red-green): **Cool to warm** using blue–cyan–yellow–orange (Oklab space if available, else HSL).

### 7.2 Area KPI charts

**Bar or column charts** (backtest, zone trends) use a single blue (`--blue`) for actual and amber (`--amber`) for expected. Pattern overlay (hatching) for colour-blind users, not colour alone.

- **Legend:** Text labels, not colour chips alone
- **Axis labels:** Zone ID, day of week, or time
- **Grid:** Subtle `--line-soft` (not white)

### 7.3 Time-series (claim tracker)

**Vertical stepper:** Each claim step is a row with a connecting line, icon (circle, check, X), label, timestamp and reason. No animation here; solid colour conveys state. See § 5.2 above.

---

## 8. Responsive rules

### 8.1 Console (desktop, 1280×720 min)

**Grid:** Left column (372 px) for phone + controls; right (flexible) for console content (map, panel, claims).

- Gaps: `--sp-6` (24 px) between columns
- Padding: `--gutter` (14 px) on sides
- Font sizes: base 14 px, headings 17–26 px

### 8.2 Mini-app phone (390×844, portrait only)

**Container:** 390 px wide (with 9 px border + 14 px padding = 372 px inner, matching the WhatsApp phone simulator `phone.css` border-radius 34 px).

- Header: 52 px (status bar 8 px + phone header 44 px)
- Content: Remaining height, scrollable
- Safe area: 14 px padding on left/right (avoids notch, if any; not needed for this design but future-proof)
- Bottom controls: 46 px (keyboard input row) or 56 px (tap-to-send chips)

**Typography on phone:** base 14 px (readable on small screens), headings 17–20 px (not smaller).

### 8.3 Fallback: 375px phone, 1024px tablet

Tests on iPhone SE and iPad are secondary; primary is 390×844 (demo laptop Pixel 5 or similar). CSS media queries:

```css
@media (max-width: 480px) { /* Phone */ }
@media (min-width: 481px) and (max-width: 768px) { /* Tablet portrait */ }
@media (min-width: 769px) { /* Desktop */ }
```

---

## 9. Content rules

### 9.1 Rupee amounts

Always use tabular numerals and the ₹ symbol:
- ₹1,380 (not "Rs 1380")
- ₹58,900 (Indian numbering: 1,38,000)
- ₹4,300/day (cap or limit) — always include the unit

### 9.2 Dates

Format: **2 Oct 2026** or **02-Oct-2026** (ISO 8601 timestamps in backend only, never in UI).

### 9.3 Time

Format: **17:04** (24 h, IST, no AM/PM). Always include the day context: "17:04, Tue 19 Aug".

### 9.4 Language switching

**Hindi first, English toggle.** Every screen shows Hindi text by default (e.g., "कवर स्थिति" = "Cover status"). An English toggle is visible in the header or a language selector. Merchant's preferred language is stored in `Merchant.language` (A3, SPEC §3).

### 9.5 Amounts in Hindi and English

Policy wording and claim statements cite amounts in both languages side by side:

**Hindi (Devanagari):** "आपको ₹1,380 का भुगतान किया गया है।"  
**English (bracket):** "You have been paid ₹1,380."

### 9.6 Jargon and plain language

Replace internal terms with merchant-friendly ones:

| Internal | UI wording |
|----------|-----------|
| Area trigger | (no mention; say "Rain alert triggered, your area's sales fell 63%") |
| Insured | "Cover" or "Protected" |
| Claim decision | "Your claim: APPROVED" (with the amount and day) |
| Referral | "We're checking. A person will review and call." |
| Instalment pause | "Your loan payment for tomorrow is paused." |

---

## 10. Dark mode

**Current position:** Light theme only in the released console (`frontend/src/styles/base.css`, `paper` background, `ink` text).

**Design for future:**
- Navy header is already dark-on-light; reverse to light-on-dark in a dark theme.
- All `--navy-*` tokens are pre-defined for dark backgrounds.
- Proposed: toggle in console header (icon with sun/moon).

**Deferred:** Dark mode is not a P0 for the hackathon final.

---

## Open questions

1. Should the provider badge (Gemini, Sarvam, fallback) be always visible in N2 Ask Chhatri, or shown only on hover/in a settings pane? Owner: Omkar Kadam.

2. For the grievance ladder (N5), should the SLA clock be a numeric countdown (e.g. "18h remaining") or a visual progress ring? Owner: Omkar Kadam.

3. Do we add a dark-mode toggle to the console header before the hackathon final, or leave it light-only? Owner: Ujjwal Pardeshi.

4. Should the N1 mini-app's language toggle persist globally (all screens) or reset on each screen load? Owner: Omkar Kadam.

---

## Changelog

- 2026-10-02 · v1.1 · second fact-check pass: clarified provider badge shows Sarvam LIVE (Gemini planned in N2)
- 2026-10-02 · v1 · first draft: tokens, principles, component inventory, N1 new components.
