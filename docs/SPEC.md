# Chhatri — build specification (source of truth)

This document is the contract every part of the prototype is built against. If code and this
document disagree, this document wins until it is changed deliberately. Section numbers are
referenced from code comments and tests (`SPEC §7.3`).

---

## 0. What we are building

Chhatri is a claims engine for merchant income cover on Paytm. The prototype must demonstrate,
live, on 3 October 2026 (hackathon final):

1. **Storm replay on a live city heat map** — Mumbai wards coloured by sales vs expected; a red
   alert and a rain band hit three zones; at 17:00 the trigger fires; 312 shops are paid at 17:04;
   the next day's loan instalment is paused at 17:05.
2. **Personal claim on WhatsApp in Hindi** — the shop goes silent; Chhatri checks in; the merchant
   replies by voice; sends one photo of a hospital slip; is paid the same day. On stage this runs in
   the console's WhatsApp-style phone simulator; live WhatsApp needs the four variables in §0.1, which
   the team does not have.
3. **Payout, instalment pause and audit log** — every step is written to a tamper-evident log.
4. **Premium paid through a Paytm payment link** — SIMULATED on stage (`https://paytm.me/sim-…`). A
   staging link through the Paytm payment MCP server needs Paytm credentials (§0.1), which the team
   does not have.
5. **Three live tests** (deck slide 8): *"My loss was bigger than that."* → EXPLAINED;
   *hospital slip with a different name* → HUMAN; *"Red alert tomorrow. Cover me today."* → BLOCKED.

### 0.1 Live vs simulated (must be labelled in the UI)

| Component | Live when | Otherwise |
|---|---|---|
| Sarvam STT/TTS/chat/vision | `SARVAM_API_KEY` set | deterministic simulator |
| WhatsApp Cloud API | `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN` set | in-console phone simulator |
| Gemini chat and vision (Ask Chhatri, slip reading; flags `n2_ask_chhatri`, `n3_slip_precheck`) | `GOOGLE_API_KEY` and `GEMINI_MODEL` set (`GEMINI_VISION_MODEL` optional) | templates, the simulated slip reader |
| Paytm payment link | `PAYTM_MCP_URL` (MCP over SSE) **or** `PAYTM_MID`+`PAYTM_KEY_SECRET` (direct REST) | simulated link |
| n8n workflows | `N8N_BASE_URL` set | in-process workflow runner (same steps) |
| Cognee memory | `COGNEE_ENABLED=true` and cognee installed and LLM configured | in-process graph (networkx) |
| Open-Meteo | always allowed, but replay/backtest use cached real data in `backend/data/weather/` | — |
| Sales data, alerts feed, KYC, payouts rail, lender, Soundbox | never live | always simulated, always labelled |

`GET /api/integrations` reports each component as `LIVE` or `SIMULATED` (with flag `x6_provider_panel`, also
`FALLBACK`); the console header shows the badges. Nothing simulated may ever be presented as live.
Sarvam, Gemini and Cognee run on free tiers, so they are called only when `CHHATRI_DATA_IS_SYNTHETIC=true`
(ADR 0009); with it unset every such link is skipped and the component reads SIMULATED.

### 0.3 Feature flags

Every feature added after the first build (N1 mini-app, N2 Ask Chhatri, N3 slip pre-check, N4 voice, N5
grievance ladder, N6 consent centre, N8 Marathi, X4 lender request, X6 provider panel, X8 distress guard, H8 ops
strip, H24 what-if, H25 evaluation page, console polish, Telegram channel) ships behind one of 15 flags, off by default. They are
the names in `chhatri/features.py` (`FEATURE_NAMES`), read from `CHHATRI_FEATURES`; the console reads the same
names from `VITE_FEATURES` (`frontend/src/features.ts`), and a test keeps the two lists identical. A route whose
flag is off answers the ordinary 404 `not_found`. `GET /api/health` lists the flags that are on. The golden
numbers and strings of §17.2 assume `x4_lender_request` on (the demo flag set) and hold with the other flags off;
the scripted `make demo-check` flow stops by design at the `n3_slip_precheck` and `n6_consents` steps when those
are on.

### 0.2 Non-negotiable principles

- **The AI builds the case; code decides the money.** Only `chhatri.policy.engine` can produce an
  `APPROVED` decision. LLM output never sets an amount, never approves, never overrides a check.
- **Every money number shown to a merchant is reproducible from the numbers shown next to it**
  (§4.3). Messages about money are rendered from templates filled with decision facts, never
  free-generated.
- **Every step is audited** (§11), with simulated time and wall time.
- **Deterministic**: same seed + same scenario ⇒ identical numbers, ids, messages and audit
  hashes (except `recorded_at` wall-clock fields, which are excluded from hashes).
- **Immutable domain objects** (pydantic `frozen=True`); change = `model_copy(update=...)`.

---

## 1. Repository layout and ownership

```
backend/
  pyproject.toml                  shared (scaffold)          – do not edit in parallel waves
  chhatri/
    config.py clock.py money.py events.py ids.py   shared (scaffold)
    domain/{enums,models}.py                         shared (scaffold)
    integrations/base.py                             shared (scaffold, protocols only)
    policy/        rules.yaml rules.py engine.py checks.py explain.py         [policy]
    store/         db.py repositories.py                                       [policy]
    audit/         log.py                                                      [policy]
    ledger/        payouts.py instalments.py premiums.py                        [policy]
    cases/         service.py                                                  [policy]
    sim/           geo.py city.py calibration.py sales.py weather.py alerts.py scenarios.py slips.py   [sim]
    forecast/      features.py model.py calibrate.py                            [forecast]
    detect/        area_index.py triggers.py silent.py                          [forecast]
    integrations/  sarvam.py whatsapp.py paytm.py openmeteo.py n8n.py memory.py soundbox.py registry.py  [integrations]
    workflows/     definitions.py runner.py                                     [integrations]
    conversation/  intents.py nlu.py messages.py guard.py service.py            [conversation]
    replay/        engine.py orchestrator.py                                    [app]
    backtest/      run.py report.py                                             [app]
    api/           app.py deps.py schemas.py sse.py security.py routers/*.py   [app]
  data/            geo/ weather/ slips/ (inputs + generated geo; committed)
  artifacts/       model/ backtest/ calibration.json premiums.json (generated by make data; committed)
  scripts/         build_data.py calibrate.py demo_check.py make_slips.py
  tests/           one test module per source module, mirrors package layout
frontend/                                                                      [frontend]
n8n/workflows/*.json                                                           [infra]
docker-compose.yml Makefile .env.example docs/*.md                             [infra]
```

Packages are owned by one builder each. Shared scaffold files are read-only for builders; request
changes in your final report.

---

## 2. Tech and versions (pinned in `backend/pyproject.toml` / `frontend/package.json`)

Backend: Python 3.12, FastAPI 0.141 (native SSE via `fastapi.sse.EventSourceResponse` is
available ≥0.135 — we use `sse-starlette` 3.5 for portability), pydantic 2.13,
pydantic-settings 2.15, uvicorn 0.54, httpx 0.28, numpy 2.x, pandas 3.x, lightgbm 4.7, h3 4.5,
shapely 2.1, networkx 3.x, rapidfuzz 3.x, Pillow 12, PyYAML, python-multipart, sarvamai 0.1.34,
mcp 1.30.0 (1.x client API — **not** 2.x), paytmchecksum 1.7.0. Optional extra `memory`: cognee.
Tests: pytest 9, pytest-asyncio 1.x (`asyncio_mode = "auto"`), pytest-cov.

Frontend: Vite 8 + React 19 + TypeScript + react-leaflet 5 + leaflet 1.9; vitest; Playwright for E2E; the mini-app adds Tailwind v4, shadcn/Radix and sonner, scoped to `frontend/src/miniapp/`.
Fonts: Ubuntu + Noto Sans Devanagari, self-hosted (offline-safe), to match the deck.

---

## 3. Domain model (implemented in `chhatri/domain/models.py`)

All models are pydantic v2, `frozen=True`, `extra="forbid"`. Times are timezone-aware
`Asia/Kolkata`. Money is **integer paise** (`int`), never float. Field names below are exact.

- `Zone(id, ward, name, centroid_lat, centroid_lng, waterlogging_prone)` — `id` like `"Z7"`.
- `Merchant(id, shop_name, owner_name, owner_name_hi, kyc_name, phone, language, zone_id, lat,
  lng, h3_cell, shop_type, weekly_off, is_demo)` — `id` like `"S-0142"`; `weekly_off` is `None`
  or 0–6 (Mon=0).
- `Loan(id, merchant_id, lender_name, daily_instalment_paise, outstanding_paise)`.
- `Cover(id, merchant_id, purchased_at, starts_on, premium_per_day_paise, prepaid_through,
  status)` — `prepaid_through` is the last date whose premium has been received.
- `Alert(id, kind, level, zone_ids, issued_at, valid_from, valid_to, source, headline_en,
  headline_hi)`.
- `ZoneWindowIndex(zone_id, window_start, window_end, actual_paise, expected_paise, index_pct,
  lower_bound_pct, shops_in_index)` — one trailing window (§8.1).
- `AreaTrigger(id, zone_id, alert_id, window_start, window_end, index_pct, drop_pct,
  lower_bound_pct, shops_in_index, fired_at)`.
- `SlipExtraction(patient_name, admission_date, discharge_date, hospital_name, document_type,
  confidence, source, raw)`.
- `Claim(id, kind, merchant_id, created_at, event_date, trigger_id, silent_dates, slip,
  expected_day_paise, drop_pct)`.
- `CheckResult(code, status, severity, label_en, detail_en, observed, required)`.
- `Explanation(weekday_en, weekday_hi, expected_day_paise, drop_pct, share_pct, days,
  cap_paise, capped, amount_paise, formula_en, formula_hi)`.
- `Decision(id, claim_id, merchant_id, outcome, amount_paise, checks, rules_version, decided_at,
  decided_by, explanation, referral_reason)`.
- `Payout(id, decision_id, merchant_id, amount_paise, status, rail, created_at, credited_at,
  reference)`.
- `InstalmentPause(id, loan_id, merchant_id, instalment_date, amount_paise, reason,
  decision_id, created_at)`.
- `PremiumPayment(id, cover_id, merchant_id, amount_paise, method, covers_from, covers_to,
  status, link_id, link_url, source, created_at, paid_at)`.
- `Case(id, kind, merchant_id, claim_id, decision_id, status, opened_at, due_by, summary_en,
  summary_hi, evidence, resolution, resolved_by, resolved_at)` — `id` like `"C-2291"`.
- `Message(id, merchant_id, direction, channel, kind, text_hi, text_en, audio_url, media_url,
  card, created_at, meta)`.
- `AuditEntry(seq, at, recorded_at, actor, action, subject_type, subject_id, data, prev_hash,
  hash)`.

Enums (`chhatri/domain/enums.py`): `ShopType`, `Language`, `AlertKind`, `AlertLevel`,
`CoverStatus`, `ClaimKind`, `CheckCode`, `CheckStatus`, `Severity`, `DecisionOutcome`,
`PayoutStatus`, `PremiumMethod`, `PremiumStatus`, `CaseKind`, `CaseStatus`, `Direction`,
`Channel`, `MessageKind`, `IntegrationMode`. Values are listed in the file.

IDs (`chhatri/ids.py`): deterministic, sequence based per prefix — `D-000001` decisions,
`P-000001` payouts, `CL-000001` claims, `IP-000001` pauses, `PR-000001` premiums, `M-000001`
messages, `MD-000001` media, `PC-000001` slip pre-checks (N3), `Q-000001` cover quotes, `E-{zone}-{yyyymmdd}` area triggers; cases
start at `C-2291` (the deck's case number). Alerts are created by the simulator, not the factory:
`A-{yyyymmdd}-{nn}` numbered per issue day in issue order (e.g. `A-20250819-01`). **The IdFactory,
store, audit log and event bus are recreated on every scenario load**, so the first case opened in
the monsoon scenario is always `C-2291` and the same scenario always yields the same ids.

---

## 4. Money, rounding, display

4.1 Store integer paise. Compute with `decimal.Decimal`. Round with ROUND_HALF_UP.

4.2 Display: `₹1,380` (Indian digit grouping: `₹1,58,900`), no decimals when whole rupees,
otherwise two decimals (`₹1.80`). Implemented once in `chhatri/money.py` (`format_inr`), and
mirrored in the frontend (`formatInr`) with identical tests.

4.3 **Published numbers rule.** Every payout is computed from the *published* (displayed)
inputs so the merchant can redo the arithmetic:
- `expected_day_paise` = model expectation for the shop's full business day, **rounded to the
  nearest ₹10** (half up). Displayed as "Your usual Tuesday: ₹4,380".
- `index_pct` = zone actual / zone expected over the trigger window, as an **integer percent,
  half up**. `drop_pct = 100 − index_pct`.
- Area payout (per shop) = `round_half_up_to_rupee(share × expected_day × drop_pct / 100)`,
  then `min(…, area_daily_cap)`. With `share = 0.50`, ₹4,380 and 63 % ⇒ ₹1,379.70 ⇒ **₹1,380**.
- Personal payout = `days × min(round_half_up_to_rupee(share × expected_day), personal_daily_cap)`.
  With ₹4,380: `min(₹2,190, ₹1,500)` ⇒ **₹1,500** for one day.

---

## 5. City, zones, merchants (`chhatri/sim/geo.py`, `city.py`)

5.1 **Zones are real BMC wards** from `backend/data/geo/bmc_wards.geojson` (DataMeet, CC BY-SA
2.5 India — attribute in the UI footer). Zone ids are pilot ids, fixed by this table so the demo
matches the deck's map layout (Z7 centre, Z3 west on the coast, Z12 south-east, Z9 by the harbour):

| Zone | Ward | Name | Pilot shops |
|---|---|---|---|
| Z7 | F/S | Parel · Lalbaug | **46** |
| Z3 | G/S | Worli · Lower Parel | **141** |
| Z12 | E | Byculla | **125** |
| Z9 | M/W | Chembur | 64 |

All other wards get the remaining ids in official BMC ward order A, B, C, D, F/N, G/N, H/E, H/W,
K/E, K/W, L, M/E, N, P/S, P/N, R/S, R/C, R/N, S, T → Z1, Z2, Z4, Z5, Z6, Z8, Z10, Z11, Z13…Z24
(skipping 3, 7, 9, 12). Their shop counts are deterministic from the seed in 30–120.
`waterlogging_prone = True` for F/S, F/N, G/N, H/E, K/W, L (known Mumbai flood spots).
`scripts/build_data.py` writes `backend/data/zones.json` (id, ward, name, centroid, shops,
waterlogging_prone) and `backend/data/geo/zones.geojson` (ward polygons with zone properties).

5.2 **Hex grid**: H3 resolution 8 cells whose centre lies inside any ward polygon. Each hex has
`zone_id` (ward containing its centre). Served as GeoJSON.

5.3 **Merchants**: deterministic from `CHHATRI_SEED` (default 20251019). Shop types and typical
full-day sales (₹, lognormal around the median):

| ShopType | median day ₹ | rain sensitivity | avg ticket ₹ | hours |
|---|---|---|---|---|
| TEA_STALL | 4,000 | 0.85 | 18 | 06–22 |
| STREET_FOOD | 6,000 | 0.90 | 45 | 10–23 |
| FRUIT_VEG | 5,000 | 0.90 | 60 | 07–21 |
| KIRANA | 9,000 | 0.55 | 120 | 07–22 |
| PHARMACY | 12,000 | 0.35 | 250 | 08–23 |
| SALON | 3,500 | 0.80 | 150 | 09–21 |
| MOBILE_RECHARGE | 3,000 | 0.70 | 100 | 09–21 |

Hourly profile per type is a fixed normalised curve (peaks: tea 07–10 & 16–19; food 12–14 &
18–22, etc.). Day-of-week multipliers per type (Sun +10 % food, −30 % mobile, …). The merchant generator sets `weekly_off = None` for every merchant in Z3, Z7 and Z12 (and for
the demo merchants); the simulator outputs zero sales on a merchant's weekly-off day.

5.4 **Demo merchants (fixed, `is_demo=True`)**
- `S-0142` **Anil's Tea Stall**, owner "Anil Jadhav", `owner_name_hi` "अनिल", `kyc_name`
  "ANIL RAMESH JADHAV", Z7, near Hindmata (19.0046, 72.8424) — must be inside F/S; language hi;
  loan: daily instalment **₹600**, lender "Simulated lender (NBFC partner)". Calibrated so his
  expected Tuesday on the replay date is **₹4,380** (§17.4).
- `S-0907` **Ramesh Vada Pav**, owner "Ramesh Pawar", `owner_name_hi` "रमेश", Z3 (Worli),
  **not covered** — used for the BLOCKED test (§13.6). Uncovered merchants are never in a zone
  index and never counted in zone shop numbers (Z3 still shows 141).
- Slip-mismatch patient name: "Sunil Pawar" (§17.2).

5.5 Every other merchant: `Merchant.id` = `S-0001…` (skip demo ids), names generated from a fixed
list of common Mumbai first names + shop type label, phone `+9199000xxxxx` (fake, 10 digits
after +91). All pilot merchants have a `Cover` (purchased ≥ 60 days before the replay,
`prepaid_through` ≥ replay date) and 40 % have a `Loan` (daily instalment ₹200–₹900).

---

## 6. Sales simulator (`chhatri/sim/sales.py`, `weather.py`, `alerts.py`)

6.1 Deterministic function of (seed, merchant, date). API:

```python
@dataclass(frozen=True)
class SalesPanel:
    merchant_ids: tuple[str, ...]      # M
    start: datetime                    # IST, first hour start
    hours: int                         # H (contiguous)
    amount_paise: np.ndarray           # (M, H) int64
    txns: np.ndarray                   # (M, H) int32
    def hour_index(self, ts: datetime) -> int
    def window(self, start: datetime, end: datetime) -> "SalesPanel"

class SalesSimulator:
    def __init__(self, city: City, shocks: ShockCalendar, seed: int) -> None
    def generate(self, start_day: date, end_day: date) -> SalesPanel      # inclusive days, 24 h each
    def ground_truth(self, start_day: date, end_day: date) -> GroundTruth # per zone-day true loss, shock labels
```

6.2 Hourly sales = base_day × dow_mult × hour_profile(type, h) × festival_mult × trend ×
(1 − impact) × noise, then 0 outside opening hours and on weekly off; noise lognormal σ≈0.25 per
hour (shop-level correlated day factor σ≈0.10). `txns ~ Poisson(amount / avg_ticket)`, and
amount is 0 when txns is 0.

6.3 **Shocks (ground truth)** in `ShockCalendar`:
- **Rain**: zone hourly rain from the real Open-Meteo fixtures (Santacruz for zones with centroid
  lat ≥ 19.03, Colaba otherwise) × a per-zone-day spatial factor (lognormal σ 0.45) plus rare
  convective cells. Outside June–September rain = 0.
  Impact for the hour [h, h+1) = `sensitivity × g(r3)` where `r3` = rain (mm) in hours h−2, h−1
  and h (inclusive of the current hour) and `g(r) = 1 − exp(−r / 25)` (saturating);
  waterlogging-prone zones use `r / 18`. Example: 60 mm over 3 h, FRUIT_VEG (0.90), normal zone ⇒
  impact 0.82. Sales for the hour are multiplied by `1 − impact`.
- **Slow days**: 1.5 % of zone-days outside alerts: whole-zone dip of 25–45 %, no alert.
- **Bandh**: one fictional city-wide bandh day per season (2024-09-10 and 2025-09-09, labelled
  simulated) with a civic alert issued the previous evening, 75 % drop all day.
- **Personal closures**: each merchant has daily hazard 1/400 of a 1–4 day closure (sales 0).
- **Festivals**: Ganesh Chaturthi 10-day window (2024-09-07, 2025-08-27) +20 % food/sweets/kirana.

6.4 **Alerts feed (simulated, labelled "IMD-style nowcast · simulated")**: zone ORANGE when
forecast trailing-3h rain ≥ 30 mm, RED ≥ 60 mm; issued 60 min before the first hour that crosses
it, valid until 3 h after rain drops below threshold. Civic alerts for bandh days (issued
previous evening). The weather-only baseline in the backtest reads only the reference grid
point (§18).

6.5 Scenario overrides (§17) replace rain/shocks for the scenario day(s) with scripted values.

---

## 7. Expected-sales model (`chhatri/forecast/`)

7.1 One LightGBM **quantile** model per quantile α ∈ {0.10, 0.50, 0.90} over **shop-hour** rows
with categorical features `zone_id`, `shop_type`, and numeric features `hour`, `dow`,
`is_festival`, `month`, `shop_level` (log of the shop's trailing-8-normal-weeks median day sales,
computed strictly before the prediction date), `shop_hour_share` (shop's trailing share of its
day in that hour). Target: `amount_paise / shop_level_paise` (normalised). Prediction ×
shop_level = expected paise. This is the deck's "LightGBM per area and shop type" (area and shop
type are model features); say exactly that in docs.

7.2 Training data: normal days only — exclude zone-days with any alert, the bandh days, and
merchant-days inside personal closures (ground truth labels are *not* available in production;
we use the alert feed and "zero-txn day" as the exclusion rule, which is what production would
do). Deterministic params: `deterministic=True`, `seed=seed`, `num_threads=1` in tests,
`force_col_wise=True`. Fix quantile crossing by sorting the three predictions per row.

7.3 `ExpectedSales.expected_day(merchant_id, day) -> int paise` = Σ over business hours of the
P50 prediction; `expected_hours(merchant_ids, start, end) -> np.ndarray` P50 per hour;
`day_range(merchant_id, day) -> (p10, p50, p90)`.

7.4 **Zone lower bound (the model's range)**: conformal calibration on held-out normal days
(the last 4 weeks of the training window, not used for fitting). For each zone and each
3-hour window on those days compute `index = Σactual/Σexpected`; the zone's lower bound is the
empirical `⌊(n+1)·0.025⌋`-th smallest value (finite-sample conformal quantile, α = 0.025,
one-sided). Store per zone as `lower_bound_pct` (integer, half up). Artefacts saved under
`backend/artifacts/model/` (committed to git so the demo machine never trains at startup) with a
manifest (training window, row counts, seed, metrics: pinball loss per quantile on the calibration
set, P10–P90 coverage). The replay model is trained with `train_end = 2025-08-18` (the day before
the monsoon replay).

---

## 8. Detection (`chhatri/detect/`)

8.1 **Area index** for zone z and a window [t−3h, t): `index = Σ actual / Σ P50` over the zone's
covered, open merchants; `shops_in_index` = number of those merchants. Computed every completed
hour; the map also shows a live partial value (pro-rated current hour).

8.2 **Trigger**: at each hour boundary t, a zone triggers when ALL hold:
(a) an alert (rain or civic) for the zone is valid for the whole window [t−3h, t);
(b) each of the 3 completed hours has hourly index < `index_floor_pct` (50) **and** the 3-hour
window index < `lower_bound_pct`;
(c) `shops_in_index ≥ min_shops_in_index` (20);
(d) the zone has not already triggered that day.
All comparisons are **strictly less than** (an hour at exactly 50 % does not count).
`AreaTrigger.index_pct` = the 3-hour window index; `drop_pct = 100 − index_pct`;
`hourly_index_pct` = the three completed hours **oldest first** (t−3h, t−2h, t−1h).
Zone status for the map: `normal`, `watch` (1–2 consecutive hours below floor with alert),
`triggered`, `slow_day` (window index below lower bound but no alert, or no alert and < floor),
`no_data` (< min shops).

8.3 **Silent shop**: merchant m is *silent* on day d when its business hours on d had zero
transactions, its P10 day range > 0 (so zero is below the bottom of the range), d is not its
weekly off, and its zone was not in an area event on d. Outreach happens the next day at 11:20
if the shop still has zero transactions that morning (by 11:00). Verification is retroactive from
sales data: a personal claim's `silent_dates` are every *completed* day from the first silent day
up to yesterday that meets all of the above; today is never claimed while it is in progress.

---

## 9. Policy engine (`chhatri/policy/`) — the only layer that can approve money

9.1 Rules live in `backend/chhatri/policy/rules.yaml` (version string `pilot-0.1`), loaded into a
frozen `PolicyRules` model. Defaults:

```yaml
version: pilot-0.1
payout_share: 0.50
area:
  index_floor_pct: 50
  consecutive_hours: 3
  min_shops_in_index: 20
  daily_cap_rupees: 2500
personal:
  daily_cap_rupees: 1500
  max_auto_days: 3
  name_match_min_score: 85        # rapidfuzz token_set_ratio on normalised names, 0–100
  slip_confidence_min: 0.80
cover:
  waiting_period_days: 7
  alert_lookahead_hours: 72
annual_limit_rupees: 30000
dispute_sla_hours: 24
payout_rail_delay_minutes: 4      # trigger → money (simulated settlement rail)
instalment_pause_delay_minutes: 5
premium:
  loading: 0.35                   # premium = expected loss cost / (1 - loading), per zone
  min_per_day_rupees: 2
  first_payment_days: 30          # a payment-link purchase prepays this many days
```

Annual limit uses a **rolling 365 days** ending on the event date (no policy-year boundary).
Per-zone premiums come from the backtest (§18) and are stored in
`backend/artifacts/premiums.json` (`{zone_id: premium_per_day_paise}`); a zone with no price is an
error (X3: start-up logs it and `/api/preflight` lists it), and `min_per_day_rupees` is the floor of every entry.

9.2 **Checks** (`CheckCode`, severity). Nineteen in all; a personal claim runs fourteen of them
and an area claim nine:

| Code | Applies | Severity | Passes when |
|---|---|---|---|
| COVER_IN_FORCE | all | HARD | cover exists, `starts_on ≤ event_date`, status ACTIVE |
| PREMIUM_PREPAID | all | HARD | `prepaid_through ≥ event_date` (Insurance Act s.64VB) |
| COVER_BEFORE_ALERT | area | HARD | `purchased_at < alert.issued_at` |
| ALERT_ACTIVE | area | HARD | alert valid over the whole trigger window |
| INDEX_QUORUM | area | HARD | `shops_in_index ≥ min_shops_in_index` |
| BELOW_FLOOR | area | HARD | all 3 hourly indices < floor |
| BELOW_MODEL_RANGE | area | HARD | window index < zone lower bound |
| SILENCE_VERIFIED | personal | HARD | every claimed day is a verified silent day (§8.3) |
| SLIP_READABLE | personal | SOFT | slip present, `document_type` medical, confidence ≥ min |
| NAME_MATCHES_KYC | personal | SOFT | name score ≥ min |
| DATES_MATCH | personal | SOFT | admission ≤ each silent day ≤ (discharge or ∞) |
| HOSPITAL_IDENTIFIED | personal | HARD | the hospital named on the slip is in the directory |
| DOCTOR_IDENTIFIED | personal | HARD | the slip names a doctor and a registration number on that hospital's register |
| VERIFICATION_CONSENT | personal | SOFT | the merchant agreed to the doctor being asked |
| DOCTOR_NOT_DENIED | personal | HARD | the treating doctor has not answered "no" |
| DOCTOR_CONFIRMED | personal | SOFT | the treating doctor confirmed the patient attended |
| WITHIN_AUTO_LIMIT | personal | SOFT | silent days ≤ `max_auto_days` |
| NOT_ALREADY_PAID | all | HARD | no approved payout for (merchant, date, kind) |
| WITHIN_ANNUAL_LIMIT | all | HARD | paid in the rolling 365 days + amount ≤ annual limit |

**Check status semantics.** HARD checks are only PASS / FAIL / NOT_APPLICABLE (missing data ⇒
FAIL). SOFT checks: SLIP_READABLE is FAIL when there is no slip or `document_type` is not one of
admission_slip / discharge_summary / prescription / bill, UNSURE when confidence < min;
NAME_MATCHES_KYC is UNSURE when `patient_name` is missing or not in Latin script, FAIL when the
score < min; DATES_MATCH is UNSURE when `admission_date` is missing, FAIL when the dates do not
cover every silent day; WITHIN_AUTO_LIMIT is FAIL when silent days > `max_auto_days` (the whole
claim is REFERRED — "anything above the cap goes to a human").

**Doctor confirmation** (rule `personal.require_doctor_confirmation`, on). Every medical claim is
confirmed with the treating doctor before it pays. The slip must carry the hospital, the doctor's
name and their medical registration number; those name *which* doctor, and the way to reach them
comes from the independent directory (`chhatri/directory.yaml`), never from the slip — a contact
printed on a claimant's own slip would confirm whatever the claimant wanted. A doctor only resolves
within the hospital the slip names, so a real registration number quoted against the wrong hospital
identifies nobody. Chhatri asks only with the merchant's consent (purpose `DOCTOR_CONFIRMATION`),
and sends only the patient, the hospital, the date and the question — never the amount, the policy
or the reason, so a hospital-cash claim never reveals an illness. The request carries
`doctor_reply_delay_minutes` (2, simulated) and expires after `doctor_reply_sla_hours` (24).
Outcomes: confirmed ⇒ APPROVED; denied ⇒ DECLINED (DOCTOR_NOT_DENIED is HARD); no answer or no
consent ⇒ REFERRED, because silence is neither a confirmation nor a denial.

**Name score** (`name_match_score`): uppercase; replace every non-letter with a space; collapse
spaces; expand a single-letter token to the KYC token starting with that letter (if exactly one);
score = `rapidfuzz.fuzz.token_set_ratio(slip, kyc)` rounded to an int. Required test pairs against
"ANIL RAMESH JADHAV": "Anil R. Jadhav" ≥ 85, "Anil Jadhav" ≥ 85, "anil ramesh jadhav" = 100,
"Sunil Pawar" < 85, "Anil Pawar" < 85, "Sunil Jadhav" < 85.

9.3 **Outcome** (`evaluate_area_claim`, `evaluate_personal_claim`): any HARD fail ⇒ `DECLINED`
(amount 0, reason = first failing check). Else any SOFT fail or UNSURE ⇒ `REFERRED` (amount is
the computed amount, *not* paid; a Case is opened). Else ⇒ `APPROVED`. Pure functions: input
facts in, `Decision` out; no I/O; decided_by `"policy-engine"`.

9.4 **Officer decision** (`apply_officer_decision`): an officer can APPROVE or DECLINE a
`REFERRED` decision. Approval produces a *new* Decision with `decided_by="officer:<id>"` after
re-running every **HARD** check (an officer cannot pay an uncovered or unpaid-premium merchant,
or pay twice); SOFT checks are recorded as `WAIVED_BY_OFFICER` (a `CheckStatus`). Payout-authority
table (deck slide 8) must hold exactly:

| Case | Chhatri alone | Goes to a human |
|---|---|---|
| Area drop during an alert, index clear | Pays | Only if the merchant disputes |
| Personal claim, slip matches name and dates | Pays up to the daily cap | Anything above the cap (days beyond `max_auto_days`) |
| Slip unclear or dates don't match | Never | Always |
| Cover bought after an alert | Never | Waiting period applies |

9.5 **Cover purchase** (`evaluate_cover_purchase(merchant, now, alerts, forecasts)`): a new cover
always starts `waiting_period_days` after purchase. If there is an alert for the merchant's zone
that is valid now (`valid_from ≤ now < valid_to`) or already issued and starting within
`alert_lookahead_hours` (`issued_at ≤ now` and `valid_from < now + lookahead`), the result is `BLOCKED` for the
requested immediate start with `starts_on` = purchase date + waiting period and message
"New cover starts after the waiting period". The premium link is still offered (the merchant
may buy cover for the future). Result type `CoverQuote(outcome: BLOCKED|OK, starts_on,
premium_per_day_paise, first_payment_paise (30 days), reason_en, reason_hi)`.

9.6 **Explanation** (`explain.py`): builds `Explanation` from the decision facts. Exact formats:
- area: en `½ × ₹4,380 × 63% = ₹1,380`; hi `₹4,380 का 63% = ₹2,759.40; उसका आधा = ₹1,380`;
  capped: en `½ × ₹9,000 × 70% = ₹3,150, capped at ₹2,500`; hi `₹9,000 का 70% = ₹6,300; उसका आधा
  = ₹3,150; सीमा ₹2,500`.
- personal: en `½ × ₹4,380 = ₹2,190 a day, capped at ₹1,500 × 1 day = ₹1,500`; uncapped
  `½ × ₹2,400 = ₹1,200 a day × 2 days = ₹2,400`; hi `₹4,380 का आधा = ₹2,190 प्रतिदिन; सीमा ₹1,500 × 1
  दिन = ₹1,500`.
`½` is used when `payout_share == 0.5`, otherwise `{share_pct}% ×`.

9.7 **Premium**: per zone, `premium_per_day = max(min_per_day, expected_annual_loss_cost_per_shop
/ 365 / (1 − loading))`, expected loss from the backtest (§18). Evening settlement (21:00
simulated time) prepays the next day's premium: **gross settlement** = the merchant's own
collections that day (Σ `amount_paise` of its sales). If gross settlement ≥ premium,
`prepaid_through` advances by one day and a `PremiumPayment(method=SETTLEMENT_DEDUCTION,
status=PAID)` is recorded; otherwise it is not advanced and PREMIUM_PREPAID fails for that next
day. Scenario setup gives every pilot merchant `prepaid_through ≥ scenario day + 1`.

---

## 10. Ledger (`chhatri/ledger/`) — simulated rails

- `PayoutService.execute(decision) -> Payout`: only for `APPROVED` decisions; idempotent on
  `decision_id`; `rail="Paytm settlement (simulated)"`; `credited_at = decided_at +
  payout_rail_delay_minutes`; writes audit.
- `InstalmentService.request_holiday(merchant, event_date, decision, at) -> HolidayOutcome | None` (X4, flag
  `x4_lender_request`): after the payout is CREDITED, *asks* the merchant's lender to pause the next day's
  instalment (tomorrow relative to the event date) if the merchant has a loan and no request exists for that
  instalment; the simulated lender ("Simulated lender (NBFC partner)") decides by its own rule and answers
  `GRANTED` (the instalment moves to the end of the tenure, no penalty, and an `InstalmentPause` is
  recorded), `REFUSED` with a reason code, or `NO_RESPONSE` after one attempt within the time limit
  (`CHHATRI_LENDER_TIMEOUT_SECONDS`). A refusal or no answer never touches the payout; audited
  (`instalment.holiday_request`, `instalment.holiday_decision`, `instalment.pause` on a grant only).
  With the flag off, `pause_next(merchant, event_date, decision, at)` pauses unconditionally as before.
- `PremiumService`: `create_link(merchant, quote)` via the `PaymentLinks` integration; on paid
  callback, extend `prepaid_through`; audited.

## 11. Audit log (`chhatri/audit/log.py`)

Append-only SQLite table. `hash = sha256(canonical_json({seq, at, actor, action, subject_type,
subject_id, data, prev_hash}))` with `canonical_json = json.dumps(sort_keys=True,
separators=(",",":"), ensure_ascii=False, default=str)`. Genesis `prev_hash` = 64 zeros.
`verify()` recomputes the chain and returns `{valid, entries, head_hash, first_bad_seq}`.
Actors: `system`, `model`, `policy-engine`, `ai-agent`, `officer:<id>`, `merchant:<id>`,
`workflow:<name>`, `doctor:<registration-no>` (the treating doctor who answers a §9.2
confirmation; the question is asked by `system`, the answer is recorded as the doctor's own). Every decision stores all checks in `data`.

## 12. Cases (`chhatri/cases/service.py`)

Cases are opened for: `REFERRED` personal claims (kind `PERSONAL_CLAIM_REVIEW`), merchant
disputes (`DISPUTE`), officer-requested area reviews. `due_by = opened_at + dispute_sla_hours`.
Case ids start at **C-2291**. Evidence bundle: merchant, cover, expected vs actual (hourly),
decision + checks, slip image URL + extraction + KYC name + match score, silent days, similar
precedents from memory (§16) — when there are none the UI shows "No similar past cases yet".

---

## 13. Conversation (`chhatri/conversation/`)

13.1 Channels: WhatsApp (live only when its variables are set, §0.1) and the console phone simulator — same `ConversationService`.
Inbound: text, voice (→ STT), image (→ slip flow), button reply. Outbound: text (Hindi line +
English line, as in the deck), payout card, case chip, voice note (TTS of the Hindi text), and a
Soundbox announcement event.

13.2 **Intents** (`intents.py`, rule-based, deterministic, Devanagari + Hinglish + English):
`WHY_AMOUNT`, `DISPUTE_AMOUNT`, `REPORT_ILLNESS`, `BUY_COVER`, `COVER_STATUS`, `GREETING`,
`AFFIRM`, `DENY`, `UNKNOWN`. `nlu.py` optionally asks Sarvam chat (`sarvam-105b`, JSON schema
response) when live; the LLM result is accepted only if it is one of the intents; on any error
fall back to rules. Tests use rules only.

13.3 **Guard** (`guard.py`): any free-text LLM reply is rejected if it contains a digit sequence
not present in the decision facts, or promises money/approval; fallback = template.

13.4 **Message catalogue** (`messages.py`) — exact strings (from the deck); `{…}` filled from
facts; amounts via `format_inr`:

| Key | Hindi | English |
|---|---|---|
| AREA_PAYOUT_INTRO | `{name_hi} जी, आज भारी बारिश से आपके इलाके की बिक्री {drop}% गिरी।` | `{name_en} ji, heavy rain cut your area's sales by {drop}% today.` |
| PAYOUT_CARD | `आज के सेटलमेंट के साथ जमा` | `Credited with today's settlement` · badge `No claim needed` |
| HOLIDAY_GRANTED | `आपके लेंडर ने कल की {instalment} की किस्त रोक दी है। वह आपके लोन के अंत में चली जाती है, कोई जुर्माना नहीं।` | `Your lender has paused tomorrow's {instalment} instalment. It moves to the end of your loan with no penalty.` |
| SOUNDBOX | `Paytm par {amount} prapt hue — Chhatri se` | `{amount} received on Paytm, from Chhatri` |
| CHECKIN_SILENT | `{name_hi} जी, आपकी दुकान कल से बंद दिख रही है। सब ठीक है?` | `Your shop has been closed since yesterday. Is everything okay?` |
| ASK_SLIP | `जल्दी ठीक हो जाइए। अस्पताल की पर्ची की एक फ़ोटो भेज दीजिए।` | `Get well soon. Please send one photo of the hospital slip.` |
| PERSONAL_PAID | `{name_hi} जी, आपका दावा मंज़ूर है। {amount} आज के सेटलमेंट के साथ जमा।` | `{name_en} ji, your claim is approved. {amount} credited with today's settlement.` |
| SLIP_TO_HUMAN | `धन्यवाद। पर्ची पर नाम आपके KYC से मेल नहीं खा रहा, इसलिए हमारी टीम इसे देखेगी। 24 घंटे में जवाब मिलेगा।` | `Thank you. The name on the slip doesn't match your KYC, so our team will check it. You'll hear back within 24 hours.` |
| EXPLAIN_AREA | `आपका आम {weekday_hi}: {expected}। आज आपके इलाके की बिक्री {drop}% गिरी। छतरी खोई हुई बिक्री का आधा देती है।` | `Your usual {weekday_en}: {expected}. Your area fell {drop}%. Chhatri pays half the lost sales.` |
| DISPUTE_ACK | `ठीक है, मैं इसे हमारी टीम को भेज रहा हूँ। 24 घंटे में जवाब मिलेगा।` | `Okay, I'm sending this to our team. You'll hear back within 24 hours.` |
| CASE_CHIP | — | `Sent to a claims officer · case {case_id}` |
| COVER_BLOCKED | `नया कवर वेटिंग पीरियड के बाद शुरू होता है — {starts_on_hi} से। कल के अलर्ट पर यह लागू नहीं होगा।` | `New cover starts after the waiting period — from {starts_on_en}. It won't apply to tomorrow's alert.` |
| COVER_LINK | `आगे के लिए कवर लेना हो तो {first_payment} ({per_day}/दिन) यहाँ भरें: {url}` | `To buy cover for later, pay {first_payment} ({per_day}/day) here: {url}` |
| OFFICER_APPROVED | `{name_hi} जी, हमारी टीम ने आपका दावा मंज़ूर किया। {amount} जमा।` | `{name_en} ji, our team approved your claim. {amount} credited.` |
| OFFICER_DECLINED | `{name_hi} जी, हमारी टीम ने आपका दावा देखा। {reason_hi}` | `{name_en} ji, our team reviewed your claim. {reason_en}` |
| FALLBACK_HELP | `मैं छतरी हूँ। आप पूछ सकते हैं: "मुझे इतने पैसे क्यों मिले?" या "मेरा नुकसान ज़्यादा हुआ"।` | `I'm Chhatri. You can ask: "Why did I get this amount?" or "My loss was bigger".` |

Weekday names hi: सोमवार मंगलवार बुधवार गुरुवार शुक्रवार शनिवार रविवार. Dates hi: `27 अगस्त`.

The EDI holiday is the lender's decision (X4, [fs-03](02-product/feature-specs/fs-03-edi-holiday.md) §8, copy deck
§3.3), so the instalment line names the lender: HOLIDAY_GRANTED above, with `HOLIDAY_GRANTED_TODAY` and
`HOLIDAY_GRANTED_ON` when the instalment is due today or on another day, `HOLIDAY_REFUSED` (with the lender's
reason, `HOLIDAY_REASON_*`) and `HOLIDAY_NO_RESPONSE`. With the flag `x4_lender_request` off the BUILT
unconditional pause keeps its three lines, INSTALMENT_PAUSED (`कल की {instalment} की किस्त रोक दी गई है।` ·
`Tomorrow's {instalment} instalment is paused.`), `INSTALMENT_PAUSED_TODAY` and `INSTALMENT_PAUSED_ON`.

13.5 **Flows**
- *Area payout* (after credit): AREA_PAYOUT_INTRO → PAYOUT_CARD(amount) → HOLIDAY_GRANTED (at the
  request time, once the lender granted; HOLIDAY_REFUSED or HOLIDAY_NO_RESPONSE otherwise) → SOUNDBOX event.
- *WHY_AMOUNT*: EXPLAIN_AREA filled from the merchant's latest area decision (or personal
  equivalent). If no payout today: FALLBACK_HELP.
- *DISPUTE_AMOUNT*: open `DISPUTE` case → DISPUTE_ACK → CASE_CHIP. (Slide 8 "EXPLAINED": the
  numbers were shown and a human review is offered/opened.)
- *Silent check-in*: CHECKIN_SILENT (business-initiated ⇒ template on live WhatsApp) →
  REPORT_ILLNESS ⇒ ASK_SLIP → image ⇒ slip read ⇒ personal claim ⇒ policy engine ⇒
  APPROVED: payout + PERSONAL_PAID; REFERRED: case + SLIP_TO_HUMAN (reason text depends on the
  failing check: name / dates / unreadable).
- *BUY_COVER*: `evaluate_cover_purchase` ⇒ COVER_BLOCKED (if blocked) + COVER_LINK with a Paytm
  link (staging when live).
- Unknown ⇒ FALLBACK_HELP.

13.6 Three live tests (automated in `scripts/demo_check.py` and E2E):
- EXPLAINED: Anil asks "मुझे इतने ही पैसे क्यों मिले?" ⇒ EXPLAIN_AREA with ₹4,380 / 63 % ; then
  "मेरा नुकसान ज़्यादा हुआ।" ⇒ DISPUTE_ACK + case **C-2291** (first case after a fresh load).
- HUMAN: slip for "Sunil Pawar" ⇒ decision REFERRED (NAME_MATCHES_KYC fail) ⇒ case; no payout
  until the officer approves.
- BLOCKED: Ramesh (S-0907) "Red alert tomorrow. Cover me today." ⇒ COVER_BLOCKED; starts_on =
  purchase date + 7 days; Paytm link returned.

13.7 Live WhatsApp templates (documented in `docs/INTEGRATIONS.md`, category UTILITY, language
`hi`): `chhatri_area_payout` (params: name, drop, amount), `chhatri_checkin` (name). Outside the
24-hour window the service sends templates; inside it sends free-form messages.

---

## 14. Integrations (`chhatri/integrations/`) — verified API facts

Protocols are in `integrations/base.py` (scaffold). Each module provides `Live…` and
`Simulated…` classes; `registry.py` builds them from `Settings` and reports status. Live clients
use timeouts (10 s default, 60 s doc-ai), retry only 429/5xx with backoff (max 3), never log
secrets, and raise `IntegrationError` with a safe message.

14.1 **Sarvam** (SDK `sarvamai==0.1.34`, verified from SDK source; base `https://api.sarvam.ai`,
header `api-subscription-key`; auth failure is HTTP 403):
- STT: `client.speech_to_text.transcribe(file=(name, bytes, mime), model="saaras:v3",
  mode="transcribe", language_code="unknown"|"hi-IN", input_audio_codec="ogg"|"opus"|"webm"|…)`
  → `.transcript`, `.language_code`, `.language_probability`. REST limit 30 s audio. Accepts
  OGG/Opus (WhatsApp voice notes) and WebM (browser MediaRecorder).
- TTS: `client.text_to_speech.convert(text=…, language_code="hi-IN", model="bulbul:v3",
  speaker="ritu", pace=1.0, output_audio_codec="mp3")` → `.audios[0]` base64. Max 2,500 chars
  (v3). v3 has no pitch/loudness. Speakers are lowercase. For WhatsApp voice notes request
  `output_audio_codec="opus"` and send as `audio/ogg`; for the browser use mp3.
- Chat: `client.chat.completions(model="sarvam-105b", messages=[…], temperature=0.1,
  response_format={"type":"json_schema","json_schema":{"name":…,"schema":…}},
  max_tokens=…)` → `.choices[0].message.content`. Endpoint `POST /v1/chat/completions`.
- Vision (slip): `client.doc_ai.extract(file=[(name, bytes, mime)], schema=json.dumps(schema),
  language="en-IN", output_format="json")` → `job_id`; poll `client.doc_ai.get_status(job_id)`
  until `completed|partially_completed|failed|rejected`; `client.doc_ai.get_results(job_id)` →
  `.result` (dict) and `.annotations` (every leaf has `confidence`). Schema root `type:"object"`,
  every field needs `type` and non-empty `description`. Slip schema fields: `patient_name`,
  `admission_date` (YYYY-MM-DD), `discharge_date`, `hospital_name`, `document_type`
  (enum admission_slip | discharge_summary | prescription | bill | other). Confidence =
  `min(annotations["patient_name"]["confidence"], annotations["admission_date"]["confidence"])`,
  treating a missing field or confidence as 0. Parse defensively (a leaf may be a dict with
  `confidence` or a list of such).
- The SDK is sync-first; call it via `asyncio.to_thread` (or `AsyncSarvamAI`).

14.2 **WhatsApp Cloud API** (httpx; `https://graph.facebook.com/{WHATSAPP_GRAPH_VERSION}`,
default `v25.0` (supported until Jul 2028; v26.0 is the newest), configurable):
- Webhook GET: if `hub.mode == "subscribe"` and `hub.verify_token == WHATSAPP_VERIFY_TOKEN`
  return `hub.challenge` as `text/plain` 200, else 403.
- Webhook POST: verify `X-Hub-Signature-256 == "sha256=" + hmac_sha256(app_secret, raw_body)`
  with `hmac.compare_digest` on the **raw bytes** before parsing; 403 on mismatch. Messages at
  `entry[].changes[].value.messages[]` (`from`, `id`, `timestamp`, `type`, `text.body`,
  `audio{id,mime_type,voice}`, `image{id,mime_type,caption}`, `interactive.button_reply{id,title}`);
  statuses at `value.statuses[]`. Idempotent on message id. Always 200 quickly.
- Media download: `GET /{media-id}` (Bearer) → `{url, mime_type}` (URL valid ~5 min) → `GET url`
  with Bearer.
- Send: `POST /{phone-number-id}/messages` with `messaging_product:"whatsapp"`, `to`, `type`
  text/audio/image/interactive/template. Voice note = OGG/Opus uploaded via
  `POST /{phone-number-id}/media` (multipart: `messaging_product=whatsapp`, `type=audio/ogg`,
  `file`) then `{"type":"audio","audio":{"id":…}}`. Reply buttons ≤3, title ≤20 chars.
- 24-hour window: free-form only within 24 h of the merchant's last message; otherwise approved
  template (UTILITY). The service tracks `last_inbound_at` per merchant.
- **Recipient safety**: live WhatsApp messages are sent **only** for demo merchants
  (`is_demo=True`) and **only** to `WHATSAPP_DEMO_RECIPIENT`; every other merchant's messages are
  recorded (simulator channel) but never sent — simulated merchants have fake numbers. Inbound
  messages from `WHATSAPP_DEMO_RECIPIENT` are routed to the loaded scenario's demo merchant;
  inbound from any other number gets a polite "this is a demo" reply at most once per day.

14.3 **Paytm payment link** (verified from Paytm's payment MCP server source):
- MCP server exposes tool **`create_payment_link(recipient_name: str, purpose: str,
  customer_email: str|None, customer_mobile: str|None, amount: str|None) -> str`** returning
  `"url =<shortUrl>\nlinkId=<id>"` on success or an error string; also
  `fetch_transactions_for_link(link_id)`. It serves **SSE** (`mcp.run(transport="sse")`, path
  `/sse`). Client (mcp 1.30): `async with sse_client(url) as (r, w): async with ClientSession(r,
  w) as s: await s.initialize(); res = await s.call_tool("create_payment_link", {...})` →
  `res.isError`, `res.content[0].text`. Parse with a strict regex; anything else ⇒ error.
- Direct REST fallback (same payload the server sends): `POST {PAYTM_BASE_URL}/link/create` with
  JSON `{"body": {mid, linkType:"FIXED", linkDescription, linkName, sendSms, sendEmail,
  maxPaymentsAllowed:1, amount, customerContact:{customerName, customerEmail, customerMobile}},
  "head": {"tokenType":"AES", "signature": PaytmChecksum.generateSignature(json.dumps(body),
  PAYTM_KEY_SECRET)}}`; success when `body.resultInfo.resultStatus == "SUCCESS"`; link at
  `body.shortUrl`, id `body.linkId`. Staging base `https://securestage.paytmpayments.com`
  (production `https://secure.paytmpayments.com`) — configurable `PAYTM_BASE_URL`.
- Never send the key to the browser. Simulated links look like `https://paytm.me/sim-XXXXXX` and
  are marked SIMULATED.

14.4 **Open-Meteo**: archive `https://archive-api.open-meteo.com/v1/archive`, forecast
`https://api.open-meteo.com/v1/forecast`; params `latitude, longitude, hourly=precipitation,
timezone=Asia/Kolkata, start_date, end_date`; response `hourly.time[]`, `hourly.precipitation[]`.
Data CC BY 4.0 — attribute "Weather data by Open-Meteo.com". Fixtures in `backend/data/weather/`.
The replay and the backtest **never** call the network: they read fixtures only. The live client is
used only by `GET /api/weather/now` (Mumbai rain now, shown as a LIVE widget when
`OPENMETEO_LIVE=true`).

14.5 **n8n** (`N8N_BASE_URL`, e.g. `http://localhost:5678`): the backend POSTs to
`{N8N_BASE_URL}/webhook/chhatri-{workflow}` with a JSON payload and header
`X-Chhatri-Secret` and body `{"run_id", "workflow", "payload"}`; n8n calls back
`POST {CHHATRI_PUBLIC_URL}/internal/workflows/{step}` with the same header and body
`{"run_id", "workflow", "step", "payload"}` (payload passed through unchanged), expecting
`200 {"ok": true, "data": {"step", "status": "done"|"skipped"}}`; any non-2xx stops the n8n run.
Workflow payloads: `payout` `{decision_id, merchant_id}`; `human-review` `{case_id, merchant_id}`;
`follow-up` `{case_id}`. Step names: `execute_payout`, `credit_payout`, `request_holiday`,
`notify_merchant`, `open_case`, `notify_officer`, `check_case_sla`. Workflows: `payout` (execute_payout → credit_payout → notify_merchant → request_holiday), `human-review`
(open_case → notify_officer), `follow-up` (check_case_sla → notify_officer, both at +24 simulated hours;
there are no Wait nodes, the backend schedules each step at decision time + its offset, §24.5). The in-process
`InProcessWorkflowEngine` executes the same step list when n8n is absent. n8n never decides: every
`execute_payout` call is re-validated (decision exists, APPROVED, not executed).

14.6 **Memory** (`MemoryGraph`): `remember(fact)` and `precedents(merchant_id=None, zone_id=None,
kind=None, limit=5)`. Simulated = networkx MultiDiGraph (nodes: shop, zone, event, payout,
dispute, case, decision; edges: IN_ZONE, PAID_FOR, DISPUTED, DECIDED_BY, SIMILAR_TO). Live =
cognee (`add` + `cognify` + `search`) behind the same interface, optional extra.

14.8 **Gemini** (`GOOGLE_API_KEY`, `GEMINI_MODEL`, optional `GEMINI_VISION_MODEL`; `integrations/gemini_client.py`,
`gemini_chat.py`, `gemini_vision.py`): `POST {base}/models/{model}:generateContent` over httpx with the key only in
the `x-goog-api-key` header; used for Ask answers and slip reading, first in their chains (Gemini → Sarvam →
template or REFERRED), never for money (§0.2). No model id has a default. Tested against fakes only.

14.7 **Soundbox**: simulated only — emits a `soundbox` event with the SOUNDBOX text and TTS audio
URL (if live TTS) to the console.

---

## 15. Workflows (`chhatri/workflows/`)

`definitions.py` declares step lists; `runner.py` executes them in-process (sim) or hands them to
n8n (live). Steps call application services through a `WorkflowContext` (no direct DB access).
Timing in replay follows `payout_rail_delay_minutes` and `instalment_pause_delay_minutes`
(simulated time), independent of real latency.

## 16. Learn loop

After each decision/payout/dispute/case resolution, write a memory fact. Simulated
`precedents()` ranks facts of the requested `kind` (or any) by score: same merchant 1.0, same zone
0.7, other 0.4; ties by most recent; excludes the subject itself. The officer console shows
"Similar past cases" from `precedents`. Backtest report includes "trigger health" per zone
(false-positive/negative counts) as the signal for recalibrating triggers.

---

## 17. Replay engine and scenarios (`chhatri/replay/`)

17.1 `ReplayEngine` owns a `ManualClock`, the loaded scenario, speed (sim minutes per real
second; default 6), and play/pause/step/seek/reset. A background task advances time in 1-minute
sim steps; at each minute it runs due scheduled events; at each hour boundary it computes zone
indices, evaluates triggers, and publishes events. Seeking forward replays deterministically;
seeking backward = reset + seek.

17.2 **Scenarios** (`chhatri/sim/scenarios.py`):
- `monsoon` — **Tue 2025-08-19**, runs 08:00→20:00. Alerts: RED rain alert `A-20250818-01` for Z3, Z7, Z12, **issued Mon 2025-08-18 17:30**
  (forecast), valid Tue 14:00–20:00 — the same alert object in every scenario. Rain band 14:00–17:00+ over those zones. Z9 has a scripted
  slow day (no alert). Targets (§17.4): Z7 index 37 % (drop 63 %), Z3 38 %, Z12 47 %, Z9 61 %
  at 17:00. At 17:00 triggers fire for Z3, Z7, Z12; decisions 17:00; credits **17:04**; pauses
  **17:05**; WhatsApp + Soundbox at credit time. KPIs: 3 zones triggered, 312 shops paid,
  trigger-to-money 4 min. Z7 panel: Alert "Red alert from 14:00"; Sales "37% of expected for 3
  hours"; Cover "46 of 46 prepaid"; Paid "17:04, with the settlement"; Total "₹58,900 ·
  instalments paused". Z9 explanation: "Why Zone 9 got nothing: its sales fell to 61% on a day
  with no weather alert. That's a slow day, not a loss event, so Chhatri doesn't pay."
  After 17:05 the phone view supports the Q&A (17:12 in the deck).
- `illness` — Anil silent all of **Wed 2025-08-20** (zone normal); replay **Thu 2025-08-21**
  10:30→13:00; outreach 11:20; voice reply; slip `anil_admission_slip.png` (patient
  "Anil R. Jadhav", admitted 2025-08-20, "Viral fever", KEM Hospital, Parel, **Dr S. Rao,
  reg. MMC-2011-45817**). Consent to confirm, the doctor asked on the chat the officer's link
  enrolled, and the confirmation back, all at **11:21** ⇒ APPROVED ₹1,500 at 11:21; credit
  **11:25**; Thursday's (next day's) instalment paused at **11:26**.
- `illness_denied` — the same timeline with the hospital register showing no such visit: the doctor
  answers no at 11:21 ⇒ DECLINED, nothing is paid, and the merchant is told the hospital's answer.
- `illness_no_answer` — the doctor does not answer within `doctor_reply_sla_hours` ⇒ REFERRED with
  the amount already computed; an officer calls the hospital on the directory number.
- `illness_mismatch` — same timeline, slip `mismatch_admission_slip.png` (patient "Sunil Pawar")
  ⇒ REFERRED ⇒ case; the officer approves in the console ⇒ ₹1,500.
- `buy_cover` — **Mon 2025-08-18** 18:00→19:00; alert `A-20250818-01` (issued 17:30) is in the
  feed; Ramesh (Z3) sends "Red alert tomorrow. Cover me today." at 18:10 ⇒ BLOCKED; starts_on
  **2025-08-25**; Paytm link for 30 days of premium.

17.3 The orchestrator (`replay/orchestrator.py`) wires detect → claims → policy → workflows →
ledger → conversation → memory → audit, and is the same code path used by the live API (the
replay only controls the clock and the data source).

17.4 **Calibration** (`scripts/calibrate.py`): deterministic search over (a) Anil's base level so
his expected Tuesday rounds to ₹4,380, (b) per-zone scenario rain impact so window indices are
Z7 37 %, Z3 38 %, Z12 47 %, (c) Z9 slow-day depth so it shows 61 %, (d) a common scale on Z7's
other merchants (then one merchant fine-tuned) so Z7's total is ₹58,900. Results are written to
`backend/artifacts/calibration.json` (committed) and consumed by the simulator. The replay date is
fixed: **Tue 2025-08-19**. `tests/test_golden_numbers.py`
asserts every golden number in this section; if generation or the model changes, re-run
calibration.

---

## 18. Backtest (`chhatri/backtest/`)

Replays **two past monsoons** (1 Jun–30 Sep 2024 and 2025) on simulated sales driven by the real
Open-Meteo rainfall fixtures, with rolling-origin models (2024 season: trained on Jan–May 2024;
2025 season: trained on Jan 2024–May 2025). Compares Chhatri's trigger (§8.2) against a
**weather-only trigger** (reference grid point daily rain ≥ 64.5 mm, IMD "heavy", pays every
covered shop in the zones mapped to that grid point `share × expected_day × 50 %`). Ground-truth
"real drop" = zone-day whose true shock-caused loss ≥ 40 % of expected day sales. Metrics per
trigger: real drops paid (recall), payouts with no real drop (false positives), trigger→money
(same day), documents per area claim (0), doubtful personal claims seen by a human (100 %),
premiums vs payouts per zone (loss ratio) with the premium from §9.7. Output
`backend/artifacts/backtest/report.json` + `report.md` (committed), plus
`backend/artifacts/premiums.json`; served at `GET /api/backtest`. All labelled
"simulated sales · real Open-Meteo rainfall".

---

## 19. HTTP API (`chhatri/api/`)

All JSON; errors use the envelope `{"ok": false, "error": {"code", "message", "fields"?}}`
(`fields` maps input names to reasons for validation errors); successes
`{"ok": true, "data": …}` (lists add `"meta": {"total", "limit", "offset"}`). Officer and
internal routes need `Authorization: Bearer <CHHATRI_OFFICER_TOKEN>` / `X-Chhatri-Secret`.
CORS allows `CHHATRI_CONSOLE_ORIGIN`. Simple in-memory rate limits on webhook, upload, message and what-if routes.
Uploads: images ≤ 5 MB (jpeg/png/webp), audio ≤ 5 MB and ≤ 30 s (ogg/opus/webm/mp3/wav/m4a).

| Method & path | Purpose |
|---|---|
| GET /api/health | `{status, version, seed}` |
| GET /api/integrations | list of `{name, mode, detail}`; with flag `x6_provider_panel` 17 rows (adds `gemini_chat`, `gemini_vision`) with `mode` LIVE, SIMULATED or FALLBACK and `provider`, `model`, `fallback_reason`, `switchable`, `forced`, `last_call` |
| POST /api/integrations/{component}/fallback `{force}` | Officer. X6 demo switch: forces a component into its fallback path or releases it; answers the updated row; audit `integration.fallback_set` (flag `x6_provider_panel` and demo mode: 404 otherwise; 409 when the component cannot be forced) |
| GET /api/session | demo mode only: `{officer_token}` (404 when `CHHATRI_DEMO_MODE=false`) |
| GET /api/preflight | readiness: artefacts loaded, scenario loadable, integrations, clock; each `{name, ok, detail}` |
| GET /api/weather/now | live Open-Meteo rain for Mumbai (only when `OPENMETEO_LIVE=true`) |
| GET /api/geo/zones | GeoJSON (ward polygons, zone props) |
| GET /api/geo/hexes | GeoJSON (H3 r8 cells, `h3`, `zone_id`, `shops`) |
| GET /api/state | full snapshot (clock, zones, hexes, kpis, triggers, feed) |
| GET /api/zones/{id} | zone panel (§17.2) |
| POST /api/replay/load `{scenario}` | load scenario (resets state) |
| POST /api/replay/play `{speed?}` · /pause · /step `{minutes}` · /seek `{to:"HH:MM"}` · /reset | clock control |
| GET /api/stream | SSE (§19.1) |
| GET /api/merchants?zone_id=&q=&limit=&offset= | list |
| GET /api/merchants/{id} | merchant, cover, loan, expected today, payouts, decisions |
| GET /api/merchants/{id}/messages | conversation |
| GET /api/merchants/{id}/cover | N1 cover card with the derived status (WAITING, ACTIVE, ...), zone price and waiting period (data-model 5.1; no flag) |
| GET /api/merchants/{id}/claims | N1 claim tracker: one item per claim and dispute with its five steps and the lender's answer (data-model 5.1; no flag) |
| POST /api/merchants/{id}/messages `{text}` | inbound text from the phone simulator |
| POST /api/merchants/{id}/voice (multipart `file`) | inbound voice (STT) |
| POST /api/merchants/{id}/voice-demo `{key}` | canned voice note (`why`, `dispute`, `ill`, `cover`) |
| POST /api/merchants/{id}/photo (multipart `file`) or `{sample}` | inbound slip |
| GET /api/cases?status= · GET /api/cases/{id} | officer queue |
| POST /api/cases/{id}/approve `{note}` · /decline `{note}` | officer action (auth) |
| GET /api/decisions/{id} · GET /api/payouts?zone_id=&date= | records |
| GET /api/decisions/{id}/receipt | H2, H3, H13, H14 decision receipt: checks with sources, the verified counterfactual, audit position, payout, lender answer, grievance path (data-model 5.8; no flag) |
| GET /api/audit?after=&limit= · GET /api/audit/verify | audit |
| GET /api/policy | rules + authority table |
| GET /api/backtest | backtest report |
| POST /api/premium/link `{merchant_id, consents?, notice_version?}` | premium link (auth); `consents` and `notice_version` matter only with `n6_consents` |
| POST /api/merchants/{id}/ask `{question, lang?, stt_id?, confirmed_mentions?}` | N2 Ask Chhatri: rules answer known intents, UNKNOWN text goes down the Gemini → Sarvam → template chain; clause chips (H17), facts with sources, next action (H21), scam warning (H19), H26 label; 409 `mentions_unconfirmed` for an unconfirmed voice chip (flag `n2_ask_chhatri`: 404 while off; rate group `messages`; data-model 5.2) |
| POST /api/voice/stt | N4 speech to text: multipart `{merchant_id, file, lang_hint?}` or JSON `{merchant_id, transcript, source: "browser"}`; transcript, one chip per amount or date (H18), H26 label; audio is not stored (flag `n4_voice`: 404 while off; rate group `uploads`; data-model 5.11) |
| POST /api/voice/tts `{merchant_id, ask_id, lang}` | N4 text to speech of an earlier answer only: `audio_url` under `/api/media/` or null so the browser speaks it (flag `n4_voice`; rate group `uploads`) |
| POST /api/merchants/{id}/slip-precheck | N3 slip pre-check, flag `n3_slip_precheck` (data-model 5.3; mock: `frontend/src/mock/precheckRoutes.ts`) |
| POST /api/merchants/{id}/slip-precheck/{precheck_id}/confirm | confirm or send to the team, flag `n3_slip_precheck` |
| POST /api/webhooks/paytm | payment callback (form or JSON) |
| GET,POST /webhooks/whatsapp | WhatsApp webhook |
| POST /internal/workflows/{step} | n8n callbacks (secret) |
| GET /api/media/{id} | stored audio/image bytes |
| GET /api/ops/summary | H8 ops counts at the replay clock: open cases, next due, claims decided by the engine, money paid today, holiday requests (flag `h8_ops_strip`: 404 while off; 409 before a load) |
| POST /api/whatif/area `{zone_id, at?, overrides?, example_merchant_id?}` | H24 read-only recompute of a zone's trigger with edited inputs, and one shop's amount arithmetic (flag `h24_whatif`: 404 while off; rate group `whatif`, 300 a minute) |
| GET,POST /api/merchants/{id}/grievances | N5 grievance ladder (H22): GET lists newest first with the ladder, clocks and next action; POST `{action: OPEN\|ESCALATE\|RESOLVE, ...}` opens (201, 200 for a repeat), escalates or resolves. A dispute opens the same DISPUTE case as the chat path (flag `n5_grievances`: 404 while off; group `messages` on the write; data-model 5.4) |
| GET /api/merchants/{id}/consents | N6 consent centre: the three purposes with state, notice texts and held slips (flag `n6_consents`: 404 while off; data-model 5.5) |
| GET /api/merchants/{id}/consents/activity | H23 what was used, for what and when: a projection of the audit log through a fixed map, newest first, `limit`, `offset`, `purpose` (flag `n6_consents`) |
| POST /api/merchants/{id}/consents/{consent_id}/withdraw | N6 turn one purpose off (officer token; 409 `already_withdrawn`, 409 `case_open`; flag `n6_consents`; group `messages`) |
| POST /api/merchants/{id}/slips/{slip_id}/forget | H23 erase one stored slip (officer token; 409 `case_open`, 409 `already_erased`; the audit log is never edited; flag `n6_consents`; group `messages`) |
| GET /api/merchants/{id}/channel | Telegram channel: the merchant's preferred channel (`whatsapp` default or `telegram`), the mode of each channel (LIVE, SIMULATED, FALLBACK) and whether a Telegram chat is linked, with the `https://t.me/<bot>?start=S-0142` deep link once the bot's username is known (flag `telegram_channel`: 404 while off; data-model 5.0) |
| POST /api/merchants/{id}/channel `{channel: "whatsapp"\|"telegram"}` | Telegram channel: choose where this merchant's notifications go (officer token; repeat is a no-op; audit `channel.preference_set`; flag `telegram_channel`; group `messages`; the choice lasts for the scenario run) |
| GET /api/evals/summary | H25 results of the offline evaluation suites, read from `backend/artifacts/evals/summary.json` (flag `h25_evals`: 404 while off; 200 with every suite `NOT_MEASURED` when no run is stored; no provider call, no rate group) |

19.1 SSE events (`event:` = type, `id:` = event id, `data:` = JSON `{id, type, at, data}` with
`data` shaped as below, types from §19.2): `scenario {clock: ClockState}` (load/reset),
`tick {clock: ClockState}` (≤ 4 per real second), `zone {zone: ZoneSnapshot}`,
`hexes {hexes: Record<h3, number|null>}` (at most once per simulated 15 min), `alert {alert: Alert}`,
`trigger {trigger: AreaTrigger}`, `decision {decision: Decision}`, `payout {payout: Payout}`,
`instalment {pause: InstalmentPause}`, `message {message: Message}`,
`soundbox {merchant_id, text, amount_label, audio_url: string|null}`, `case {case: Case}`,
`audit {seq, action, actor, subject_type, subject_id}`, `kpis {kpis: Kpis}`. The client resumes
with `Last-Event-ID`. Keep-alive ping every 15 s (sse-starlette `ping=15`).


### 19.2 Response shapes (TypeScript notation; mirrored in `frontend/src/api/types.ts` and pydantic
schemas in `chhatri/api/schemas/`). Money fields end in `_paise` (integer) and are always
accompanied by a preformatted `*_label` string from `format_inr` so the UI never re-derives money.

```ts
type Envelope<T> = { ok: true; data: T; meta?: { total: number; limit: number; offset: number } }
                 | { ok: false; error: { code: string; message: string } };

type IntegrationStatus = { name: "sarvam_stt"|"sarvam_tts"|"sarvam_chat"|"sarvam_vision"|"whatsapp"|"paytm"|"n8n"|"memory"|"weather"|"soundbox"|"sales_data"|"alerts"|"payout_rail"|"lender"|"kyc";
                           mode: "LIVE"|"SIMULATED"; detail: string };
// Flag x6_provider_panel on (data-model 5.6): 17 rows, the 15 above then "gemini_chat"|"gemini_vision", each
type ProviderRow = { name: IntegrationStatus["name"] | "gemini_chat" | "gemini_vision"; mode: "LIVE"|"SIMULATED"|"FALLBACK";
                     detail: string; provider: string; model: string | null; fallback_reason: string | null;
                     switchable: boolean; forced: boolean; last_call: { at: string; outcome: string; ms: number } | null };

type ClockState = { now: string /* ISO IST */; scenario: ScenarioName | null; scenario_title: string;
                    running: boolean; speed: number /* sim minutes per real second */; start: string; end: string;
                    label: string /* e.g. "Mumbai · monsoon replay · 17:00 · simulated" */ };
type ScenarioName = "monsoon" | "illness" | "illness_mismatch" | "buy_cover";

type ZoneStatusName = "normal" | "watch" | "triggered" | "slow_day" | "no_data";
type ZoneSnapshot = { zone_id: string; ward: string; name: string; shops: number;
                      index_pct: number | null; live_index_pct: number | null; lower_bound_pct: number;
                      status: ZoneStatusName; hours_below: number;
                      alert: { id: string; level: "YELLOW"|"ORANGE"|"RED"; kind: "RAIN"|"CIVIC"|"HEATWAVE"; valid_from: string; valid_to: string; headline_en: string } | null;
                      label: string /* "Z7 · 37% · 46 shops" */ };

type Kpis = { zones_triggered: number; shops_paid: number; trigger_to_money_min: number | null;
              total_paid_paise: number; total_paid_label: string; instalments_paused: number };

type FeedItem = { id: number; at: string; type: string; text_en: string; zone_id?: string; merchant_id?: string };

type StateSnapshot = { clock: ClockState; zones: ZoneSnapshot[]; hexes: Record<string /* h3 */, number | null>;
                       kpis: Kpis; triggers: AreaTrigger[]; explanations: Record<string /* zone_id */, string>;
                       feed: FeedItem[]; demo_merchant_id: string | null; rain_band: GeoJSON.FeatureCollection | null };

type Alert = { id: string; kind: "RAIN"|"CIVIC"|"HEATWAVE"; level: "YELLOW"|"ORANGE"|"RED"; zone_ids: string[];
               issued_at: string; valid_from: string; valid_to: string; source: string; headline_en: string; headline_hi: string };
type InstalmentPause = { id: string; loan_id: string; merchant_id: string; instalment_date: string; amount_paise: number;
                         amount_label: string; reason: string; decision_id: string; created_at: string };

type AreaTrigger = { id: string; zone_id: string; alert_id: string; window_start: string; window_end: string;
                     index_pct: number; drop_pct: number; hourly_index_pct: number[]; lower_bound_pct: number;
                     shops_in_index: number; fired_at: string };

type ZonePanel = { zone: ZoneSnapshot; triggered: boolean;
                   rows: { label: "Alert"|"Sales"|"Cover"|"Paid"|"Total"; value: string }[];  // exact deck strings (§17.2)
                   explanation: string | null; shops_paid: number; total_paid_paise: number; total_paid_label: string;
                   hourly: { hour: string; index_pct: number | null }[] };

type Check = { code: string; status: "PASS"|"FAIL"|"UNSURE"|"NOT_APPLICABLE"|"WAIVED_BY_OFFICER"; severity: "HARD"|"SOFT";
               label_en: string; detail_en: string; observed: string | null; required: string | null };
type Explanation = { weekday_en: string; weekday_hi: string; expected_day_paise: number; expected_day_label: string;
                     drop_pct: number | null; share_pct: number; days: number; cap_paise: number; capped: boolean;
                     amount_paise: number; amount_label: string; formula_en: string; formula_hi: string };
type Decision = { id: string; claim_id: string; merchant_id: string; outcome: "APPROVED"|"REFERRED"|"DECLINED";
                  amount_paise: number; amount_label: string; checks: Check[]; rules_version: string; decided_at: string;
                  decided_by: string; explanation: Explanation | null; referral_reason: string | null; supersedes: string | null };
type Payout = { id: string; decision_id: string; merchant_id: string; amount_paise: number; amount_label: string;
                status: "PENDING"|"CREDITED"|"FAILED"; rail: string; created_at: string; credited_at: string | null; reference: string };

type MerchantSummary = { id: string; shop_name: string; owner_name: string; zone_id: string; shop_type: string;
                         lat: number; lng: number; is_demo: boolean; covered: boolean };
type MerchantDetail = MerchantSummary & { owner_name_hi: string; kyc_name_masked: string; phone_masked: string; language: string;
                         cover: { status: string; starts_on: string; prepaid_through: string | null; premium_per_day_label: string } | null;
                         loan: { daily_instalment_label: string; lender_name: string } | null;
                         expected_today_label: string | null; payouts: Payout[]; decisions: Decision[] };

type Message = { id: string; merchant_id: string; direction: "INBOUND"|"OUTBOUND"; channel: "WHATSAPP"|"SIMULATOR"|"SOUNDBOX";
                 kind: "TEXT"|"VOICE"|"IMAGE"|"PAYOUT_CARD"|"CASE_CHIP"|"SOUNDBOX"|"TEMPLATE"|"BUTTONS";
                 text_hi: string | null; text_en: string | null; audio_url: string | null; media_url: string | null;
                 card: { amount_label: string; subtitle_hi: string; subtitle_en: string; badge: string; footer_en?: string } | null;
                 created_at: string; meta: { transcript?: string; voice_source?: "sarvam"|"browser-simulated"; duration_s?: number; case_id?: string } };

type Case = { id: string; kind: "PERSONAL_CLAIM_REVIEW"|"DISPUTE"|"AREA_REVIEW"; merchant_id: string; merchant_name: string;
              status: "OPEN"|"APPROVED"|"DECLINED"|"CLOSED"; opened_at: string; due_by: string; summary_en: string;
              decision: Decision | null; evidence: CaseEvidence; resolution: string | null; resolved_by: string | null; resolved_at: string | null };
type CaseEvidence = { expected_vs_actual?: { hour: string; expected_paise: number; actual_paise: number }[];
                      slip?: { media_url: string; patient_name: string | null; admission_date: string | null; discharge_date: string | null;
                               hospital_name: string | null; document_type: string | null; confidence: number; source: string };
                      kyc_name?: string; name_score?: number; silent_days?: string[]; merchant_text?: string;
                      precedents?: { subject_id: string; kind: string; at: string; text: string }[] };

type AuditEntry = { seq: number; at: string; recorded_at: string; actor: string; action: string; subject_type: string;
                    subject_id: string; data: Record<string, unknown>; prev_hash: string; hash: string };
type AuditVerify = { valid: boolean; entries: number; head_hash: string; first_bad_seq: number | null };

type PolicyView = { rules: Record<string, unknown>; authority: { case: string; alone: string; human: string }[];
                    checks: { code: string; severity: "HARD"|"SOFT"; applies: "area"|"personal"|"all"; passes_when: string }[] };

type BacktestReport = { label: string; seasons: string[]; generated_at: string;
                        triggers: { name: "chhatri"|"weather_only"; real_drops: number; real_drops_paid: number; recall: number;
                                    payouts: number; payouts_no_real_drop: number; false_positive_rate: number; paid_paise: number;
                                    trigger_to_money: string; documents_per_area_claim: number }[];
                        zones: { zone_id: string; premium_per_day_label: string; premiums_paise: number; payouts_paise: number; loss_ratio: number;
                                 chhatri_fp: number; chhatri_fn: number }[];
                        personal: { claims: number; auto_paid: number; referred: number; referred_share: number };
                        notes: string[] };
```

---

## 20. Console (`frontend/`)

Routes: `/` Overview homepage (the whole idea, deck-grade: problem, how it works, the storm example, WhatsApp journeys, humans in control, backtest proof, tech, roadmap, team, with calls to action into the live demo) · `/live` Live map · `/claims` officer queue · `/merchant/:id` phone · `/audit` · `/backtest`
· `/policy`. Header: Chhatri wordmark, scenario picker, clock ("Mumbai · monsoon replay · 17:00 ·
simulated"), play/pause/speed/seek, integration badges (LIVE green / SIMULATED grey).

- **Live map**: Leaflet over OpenStreetMap standard tiles (softly muted, with their attribution;
  `VITE_TILE_URL` swaps the source); a failing tile layer falls back to a map drawn from the ward outlines.
  The heat is a wash, not a grid: H3 hexes coloured by sales vs expected on the deck's scale (40 % red →
  70 % amber → 100 %+ green; legend "Pays below 50% for 3 h, with alert"), blurred and multiplied onto
  the tiles so place, district and sector names stay readable; navy ward hairlines. A "Mumbai | MMR"
  switch frames the storm or the whole Mumbai Metropolitan Region, where the cells outside the 24 covered
  wards carry a fainter simulated wash (display only, labelled, never a payout); zone labels
  "Z7 · 37% · 46 shops"; Anil's pin with "₹1,380 paid · 17:04" after credit; rain band overlay
  during alerts; right panel = triggered zone card, KPI tiles (zones triggered, shops paid,
  trigger to money), "Why Zone 9 got nothing"; live event feed.
- **Claims**: case list (id, kind, merchant, age, SLA), case detail with evidence, checks
  (pass/fail/soft), slip image + extraction + KYC name + score, precedents, Approve/Decline one
  tap; decision result inline.
- **Merchant phone**: WhatsApp-like UI (Paytm · Chhatri header, "Merchant protection · Hindi,
  English"), Hindi line + English line bubbles, payout card, case chip, voice notes (play Bulbul
  audio when live; browser `speechSynthesis` hi-IN when simulated, labelled), quick chips for the
  demo utterances, text box, mic record (live STT), photo upload + sample slips, Soundbox strip.
- **Sound**: browsers block autoplay, so the header has an **Enable sound** toggle; the
  presenter clicks it once (a user gesture) and afterwards Soundbox announcements and incoming
  voice notes auto-play. Every voice bubble also has a play button with duration.
- **Resilience**: tiles failing ⇒ plain background with ward outlines (no broken-image grid);
  SSE drop ⇒ auto-reconnect with `Last-Event-ID` and a small "reconnecting" pill; every fetch has
  a visible error state. All fonts (Ubuntu, Noto Sans Devanagari) are self-hosted in
  `frontend/public/fonts/` so the console works offline.
- **Audit**: table + "Verify chain" → valid/invalid.
- **Backtest**: metrics table Chhatri vs weather-only, per-zone loss ratios, labelled.
- **Policy**: payout authority table + rules from `/api/policy`.
- **Evals** (`/evals`, flag `h25_evals`): the results of the offline evaluation suites, or NOT MEASURED.
- **Merchant mini-app** (flag `n1_miniapp`): a phone-sized app (`frontend/src/miniapp/`, Tailwind v4 and shadcn
  scoped under `.miniapp`) as a third column beside the phone on `/merchant/:id` and as a standalone page at
  `/merchant/:id/app`; Hindi and English, Marathi behind `n8_marathi`. It reads the same API and mock backend as
  the console ([ADR 0005](04-engineering/adr/0005-mini-app-inside-the-console.md)).
- **Provider panel and ops strip** (flags `x6_provider_panel`, `h8_ops_strip`, `h24_whatif`): the header panel
  with the fallback switches, the ops counts, and the what-if drawer.
Design tokens from the deck: navy `#0f1a33`, ink `#0f172a`, blue `#0b63c9`, accent `#38a3e8`,
paper `#f3f5f8`, amber `#e39a4f`, red `#b91c1c`, green `#15803d`, WhatsApp header `#0b3d2e`,
chat bg `#ece5dd`, bubble out `#d9fdd3`. Works at 1280×720 (projector) and on phones.

---

## 21. Security

Secrets only from env (`.env`, never committed; `.env.example` lists names). Validate every
input with pydantic; webhooks verify signatures; internal routes need the shared secret; officer
routes need the officer token (demo token printed at startup when unset); uploads type/size
checked by magic bytes, not just headers; no PII in logs (mask phone numbers `+91•••••12345`);
errors never echo secrets or stack traces; CORS restricted; rate limits on webhooks/uploads.

## 22. Testing and acceptance

- `pytest` with coverage ≥ 80 % for `chhatri/`; one test module per source module.
- Golden-number test (§17.4) and the three live tests (§13.6) are mandatory.
- Policy engine tests cover every row of §9.2 and the authority table (§9.4).
- Audit chain tamper test. Webhook signature tests. Guard tests.
- `scripts/demo_check.py` runs every scenario through the HTTP API and asserts the outcomes.
- Frontend: vitest for formatters/colour scale, the console and the mini-app; Playwright E2E (projects `mock` and
  `live`) for the monsoon replay, the officer approve flow and the mini-app flows.
- Route table: `backend/tests/api/test_route_table.py` pins §19 to exactly 60 routes, with their auth.
- Feature flags: every flagged route answers 404 while its flag is off (`tests/api/test_feature_routes.py`), and
  the golden numbers hold with every flag off.
- Infra: `scripts/tests/` (n8n workflows generated from `WORKFLOWS`, compose, env, nginx, Makefile).

## 23. Developer commands

The ASGI app is the factory `chhatri.api.app:create_app` (`uvicorn --factory`).
`make setup` (venv + deps + npm ci), `make data` (exactly one command:
`python backend/scripts/build_data.py`, which runs geo → city → history → model → calibration →
backtest and writes `artifacts/MANIFEST.json`), `make test` (fast suite: `-m "not slow"`; it must
NOT depend on `make data`), `make test-slow` (golden numbers + full-artefact flows), `make dev`
(uvicorn :8000 + vite :5173), `make demo-check` (`python backend/scripts/demo_check.py`), `make e2e`
(Playwright against a running backend + console), `make up` (docker compose: backend, frontend,
n8n with auto-imported workflows). Also: `make test-backend`, `make test-frontend`, `make test-slow`,
`make test-infra`, `make lint`, `make evals` (offline evaluation suites), `make env` (create `.env`),
`make check-keys` (which keys are set; never prints them), `make n8n-workflows`, `make n8n-selftest`,
`make down`. `make demo-check` runs in process with `CHHATRI_FEATURES=x4_lender_request`.

---

## 24. Module interfaces (exact — builders implement these signatures)

Where this section and earlier prose differ on a signature, **this section wins**. Value types that
several packages share are already implemented in the scaffold and are read-only:
`chhatri/sim/types.py` (Hex, Geography, ShopProfile, City, SalesPanel, GroundTruth,
ScenarioOverrides, Scenario, Calibration), `chhatri/detect/types.py` (ZoneState, SilentFinding),
`chhatri/policy/facts.py` (AreaClaimFacts, PersonalClaimFacts — note the field
`paid_last_365_days_paise`), `chhatri/store/protocols.py` (AuditSink, MessageLog),
`chhatri/policy/rules.py` (PolicyRules, `default_rules()`). The listings below repeat some of them
for reference; import them, do not redefine them.

Conventions: frozen dataclasses (`@dataclass(frozen=True, slots=True)`) for internal value types,
pydantic models for anything crossing HTTP. Mappings exposed publicly are `types.MappingProxyType`.
Time arguments are IST-aware datetimes; `day` arguments are `datetime.date` in IST.

### 24.1 sim

```python
# chhatri/sim/geo.py
@dataclass(frozen=True, slots=True)
class Hex:
    h3: str; zone_id: str; center_lat: float; center_lng: float

@dataclass(frozen=True, slots=True)
class Geography:
    zones: tuple[Zone, ...]                 # sorted by numeric id (Z1..Z24)
    zones_geojson: dict                     # FeatureCollection, props: id, ward, name, shops, waterlogging_prone
    hexes: tuple[Hex, ...]
    hexes_geojson: dict                     # FeatureCollection, props: h3, zone_id, shops
    def zone_of(self, lat: float, lng: float) -> str | None: ...

def build_geography(wards_geojson: Path, shops_per_zone: Mapping[str, int], resolution: int = 8) -> Geography

# chhatri/sim/city.py
@dataclass(frozen=True, slots=True)
class ShopProfile:
    merchant_id: str
    base_day_paise: int                     # typical full-day sales before dow/festival/shock/noise
    open_hour: int                          # business hours are [open_hour, close_hour)
    close_hour: int
    hour_weights: tuple[float, ...]         # len 24, zero outside business hours, sums to 1.0
    dow_mult: tuple[float, ...]             # len 7, Mon..Sun
    rain_sensitivity: float                 # 0..1
    avg_ticket_paise: int

@dataclass(frozen=True, slots=True)
class City:
    seed: int
    geography: Geography
    merchants: tuple[Merchant, ...]         # sorted by id; row order of every SalesPanel
    profiles: Mapping[str, ShopProfile]
    covers: Mapping[str, Cover]             # by merchant_id (pilot merchants only)
    loans: Mapping[str, Loan]               # by merchant_id
    @property
    def zones(self) -> tuple[Zone, ...]: ...
    def merchant(self, merchant_id: str) -> Merchant: ...          # KeyError if unknown
    def row(self, merchant_id: str) -> int: ...                     # row index in SalesPanel
    def zone_rows(self, zone_id: str) -> tuple[int, ...]: ...       # rows of merchants in zone

def build_city(seed: int, data_dir: Path, calibration: "Calibration | None" = None,
               scale: Literal["full", "small"] = "full") -> City
# "small" = only Z3 (40 shops), Z7 (46), Z9 (25), Z12 (30) incl. demo merchants — for fast tests.

# chhatri/sim/calibration.py  (owned by sim; written by scripts/calibrate.py)
@dataclass(frozen=True, slots=True)
class Calibration:
    anil_base_day_paise: int
    zone_rain_scale: Mapping[str, float]    # monsoon scenario, per triggered zone
    z9_slow_depth: float
    z7_other_scale: float
    z7_tune_merchant_id: str | None
    z7_tune_base_day_paise: int | None
def load_calibration(data_dir: Path) -> Calibration   # defaults when the file is missing

# chhatri/sim/sales.py
@dataclass(frozen=True, slots=True)
class SalesPanel: ...   # §6.1; amount_paise int64, txns int32; hour h is [start+h, start+h+1)

@dataclass(frozen=True, slots=True)
class GroundTruth:
    zone_day_loss_pct: Mapping[tuple[str, date], float]   # true shock-caused loss vs counterfactual
    zone_day_label: Mapping[tuple[str, date], str]        # "rain" | "slow_day" | "bandh" | "normal"
    closures: Mapping[str, tuple[tuple[date, date], ...]] # merchant → inclusive closure ranges

class SalesSimulator:
    def __init__(self, city: City, shocks: "ShockCalendar", seed: int) -> None
    def generate(self, start_day: date, end_day: date) -> SalesPanel
    def counterfactual(self, start_day: date, end_day: date) -> SalesPanel   # same noise, no shocks
    def ground_truth(self, start_day: date, end_day: date) -> GroundTruth

# chhatri/sim/weather.py + alerts.py
class ShockCalendar:
    def rain_mm(self, zone_id: str, hour_start: datetime) -> float
    def alerts_between(self, start: datetime, end: datetime) -> tuple[Alert, ...]   # overlapping
    def slow_day_depth(self, zone_id: str, day: date) -> float                      # 0.0 if none
    def closures(self, merchant_id: str) -> tuple[tuple[date, date], ...]
    def is_bandh(self, day: date) -> bool
def build_shocks(city: City, data_dir: Path, seed: int,
                 overrides: "ScenarioOverrides | None" = None) -> ShockCalendar

# chhatri/sim/scenarios.py
@dataclass(frozen=True, slots=True)
class ScenarioOverrides:
    rain_mm: Mapping[tuple[str, date], tuple[float, ...]]   # (zone, day) → 24 hourly values
    alerts: tuple[Alert, ...]
    slow_days: Mapping[tuple[str, date], float]
    closures: Mapping[str, tuple[tuple[date, date], ...]]
    quiet_days: tuple[date, ...]      # no random shocks on these days (scenario is fully scripted)

@dataclass(frozen=True, slots=True)
class Scenario:
    name: str; title: str; day: date; start: datetime; end: datetime
    demo_merchant_id: str
    overrides: ScenarioOverrides
    history_start: date               # first day of sales history the app generates for this scenario
    slip_sample: str | None           # "anil_admission_slip.png" | "mismatch_admission_slip.png" | None

SCENARIOS: tuple[str, ...] = ("monsoon", "illness", "illness_mismatch", "buy_cover")
def get_scenario(name: str, city: City, calibration: Calibration) -> Scenario   # ValueError if unknown

# chhatri/sim/slips.py
def render_slip(patient_name: str, admitted: date, hospital: str, diagnosis: str,
                *, sample_label: bool = True) -> bytes            # PNG with tEXt "chhatri:slip" JSON
def read_embedded_slip(png: bytes) -> dict | None                   # used by the simulated SlipReader
```

### 24.2 forecast + detect

```python
# chhatri/forecast/model.py
@dataclass(frozen=True, slots=True)
class ModelManifest:
    seed: int; train_start: date; train_end: date; calib_start: date; calib_end: date
    rows_train: int; rows_calib: int
    pinball: Mapping[str, float]            # "p10" | "p50" | "p90" on the calibration set
    coverage_p10_p90: float
    lower_bound_pct: Mapping[str, int]      # per zone (§7.4)

class ExpectedSalesModel:
    manifest: ModelManifest
    @classmethod
    def train(cls, city: City, history: SalesPanel, alerts: Sequence[Alert], *, train_end: date,
              train_weeks: int = 26, calib_weeks: int = 4, seed: int, sample_frac: float = 0.35,
              num_threads: int = 0) -> "ExpectedSalesModel"
    def save(self, directory: Path) -> None
    @classmethod
    def load(cls, directory: Path) -> "ExpectedSalesModel"
    def predict(self, city: City, history: SalesPanel, start: datetime, hours: int) -> np.ndarray
        # (M, hours, 3) float64 paise [p10, p50, p90] for every merchant row; features use only
        # history strictly before start.date() (no leakage); zero outside business hours/weekly off
    def expected_day_paise(self, city: City, history: SalesPanel, merchant_id: str, day: date) -> int
        # Σ P50 over the day, rounded half-up to paise (unrounded to ₹10 — rounding is policy's job)
    def day_range_paise(self, city: City, history: SalesPanel, merchant_id: str, day: date) -> tuple[int, int, int]
    def lower_bound_pct(self, zone_id: str) -> int

# chhatri/detect/area_index.py
def window_index(actual: SalesPanel, expected_p50: np.ndarray, rows: Sequence[int],
                 start: datetime, end: datetime) -> tuple[int, int, int | None]
    # (actual_paise, expected_paise, index_pct half-up or None when expected == 0)
def zone_window(city: City, actual: SalesPanel, expected_p50: np.ndarray, zone_id: str,
                start: datetime, end: datetime, lower_bound_pct: int) -> ZoneWindowIndex

# chhatri/detect/triggers.py
ZoneStatusName = Literal["normal", "watch", "triggered", "slow_day", "no_data"]

@dataclass(frozen=True, slots=True)
class ZoneState:
    zone_id: str; status: ZoneStatusName
    index_pct: int | None               # trailing 3 completed hours
    hourly_pct: tuple[int | None, ...]  # the 3 completed hours, oldest first
    hours_below: int                    # consecutive completed hours below floor, alert or not
    alert_id: str | None; shops_in_index: int; lower_bound_pct: int

def evaluate_hour(at: datetime, city: City, actual: SalesPanel, expected_p50: np.ndarray,
                  alerts: Sequence[Alert], lower_bounds: Mapping[str, int], rules: PolicyRules,
                  already_triggered: frozenset[tuple[str, date]]) -> tuple[tuple[AreaTrigger, ...], Mapping[str, ZoneState]]
    # `at` must be an hour boundary; evaluates windows ending at `at`

# chhatri/detect/silent.py
@dataclass(frozen=True, slots=True)
class SilentFinding:
    merchant_id: str; day: date; expected_day_paise: int; p10_day_paise: int

def find_silent(day: date, city: City, actual: SalesPanel, day_ranges: Mapping[str, tuple[int, int, int]],
                area_event_zones: frozenset[str]) -> tuple[SilentFinding, ...]
def silent_this_morning(merchant_id: str, day: date, city: City, actual: SalesPanel, until_hour: int = 11) -> bool
```

### 24.3 policy, store, audit, ledger, cases

```python
# chhatri/policy/engine.py  (pure; no I/O)
@dataclass(frozen=True, slots=True)
class AreaClaimFacts:
    claim: Claim; merchant: Merchant; cover: Cover | None; trigger: AreaTrigger; alert: Alert | None
    paid_last_365_days_paise: int; already_paid: bool; weekday: int

@dataclass(frozen=True, slots=True)
class PersonalClaimFacts:
    claim: Claim; merchant: Merchant; cover: Cover | None
    verified_silent_dates: tuple[date, ...]; kyc_name: str
    paid_last_365_days_paise: int; already_paid_dates: tuple[date, ...]; weekday: int

def publish_expected_day(expected_day_paise: int) -> int          # → nearest ₹10 (SPEC §4.3)
def area_amount(expected_day_published: int, drop_pct: int, rules: PolicyRules) -> tuple[int, bool]  # (paise, capped)
def personal_amount(expected_day_published: int, days: int, rules: PolicyRules) -> tuple[int, bool]
def evaluate_area_claim(facts: AreaClaimFacts, rules: PolicyRules, *, decision_id: str, now: datetime) -> Decision
def evaluate_personal_claim(facts: PersonalClaimFacts, rules: PolicyRules, *, decision_id: str, now: datetime) -> Decision
def apply_officer_decision(referred: Decision, facts: PersonalClaimFacts | AreaClaimFacts, *, approve: bool,
                           officer_id: str, note: str, rules: PolicyRules, decision_id: str, now: datetime) -> Decision
def evaluate_cover_purchase(merchant: Merchant, existing: Cover | None, *, now: datetime, alerts: Sequence[Alert],
                            premium_per_day_paise: int, rules: PolicyRules, quote_id: str) -> CoverQuote
def name_match_score(slip_name: str, kyc_name: str) -> int         # 0..100, normalised (case, dots, initials)

# chhatri/store/repositories.py — in-memory, thread-safe, stores frozen models, returns them unchanged
class Store:
    def __init__(self, city: City) -> None
    city: City
    def cover(self, merchant_id: str) -> Cover | None
    def put_cover(self, cover: Cover) -> None
    def add_claim(self, claim: Claim) -> None;            def claim(self, claim_id: str) -> Claim
    def add_decision(self, d: Decision) -> None;          def decision(self, decision_id: str) -> Decision
    def decisions_for(self, merchant_id: str) -> tuple[Decision, ...]        # oldest first
    def latest_paid_decision(self, merchant_id: str) -> Decision | None      # latest APPROVED with a CREDITED payout
    def add_payout(self, p: Payout) -> None;              def replace_payout(self, p: Payout) -> None
    def payout_for_decision(self, decision_id: str) -> Payout | None
    def payouts(self, *, zone_id: str | None = None, day: date | None = None) -> tuple[Payout, ...]
    def paid_last_365_days_paise(self, merchant_id: str, on: date) -> int   # CREDITED+PENDING payouts in (on-365d, on]
    def add_pause(self, pause: InstalmentPause) -> None;  def pauses(self, merchant_id: str | None = None) -> tuple[InstalmentPause, ...]
    def add_premium(self, p: PremiumPayment) -> None;     def replace_premium(self, p: PremiumPayment) -> None
    def premium_by_link(self, link_id: str) -> PremiumPayment | None
    def add_quote(self, q: CoverQuote) -> None
    def add_case(self, c: Case) -> None;                  def replace_case(self, c: Case) -> None
    def case(self, case_id: str) -> Case;                 def cases(self, status: CaseStatus | None = None) -> tuple[Case, ...]
    def add_message(self, m: Message) -> None;            def messages(self, merchant_id: str) -> tuple[Message, ...]
    def put_media(self, data: bytes, mime: str, media_id: str) -> None; def media(self, media_id: str) -> tuple[bytes, str]
    def area_trigger(self, trigger_id: str) -> AreaTrigger | None; def add_trigger(self, t: AreaTrigger) -> None
    def triggers(self) -> tuple[AreaTrigger, ...]

# chhatri/audit/log.py
class AuditLog:
    def __init__(self, path: Path | None = None) -> None       # None → in-memory SQLite
    def append(self, *, at: datetime, actor: str, action: str, subject_type: str, subject_id: str,
               data: Mapping[str, Any]) -> AuditEntry
    def entries(self, *, after: int = 0, limit: int = 200) -> tuple[AuditEntry, ...]
    def verify(self) -> dict                                    # {valid, entries, head_hash, first_bad_seq}
    def head_hash(self) -> str
    def __len__(self) -> int

# chhatri/ledger/*.py
class PayoutService:
    def __init__(self, store: Store, audit: AuditLog, ids: IdFactory, rules: PolicyRules) -> None
    def execute(self, decision: Decision) -> Payout      # APPROVED only; idempotent on decision.id; PENDING, credited_at None
    def credit(self, payout_id_or_decision_id: str, at: datetime) -> Payout   # → CREDITED (idempotent)
class InstalmentService:
    def __init__(self, store: Store, audit: AuditLog, ids: IdFactory) -> None
    def pause_next(self, merchant_id: str, event_date: date, decision: Decision, at: datetime) -> InstalmentPause | None
class PremiumService:
    def __init__(self, store: Store, audit: AuditLog, ids: IdFactory, rules: PolicyRules, links: PaymentLinks) -> None
    async def create_link(self, merchant: Merchant, quote: CoverQuote, at: datetime) -> PremiumPayment
    def mark_paid(self, link_id: str, at: datetime, txn_id: str | None) -> PremiumPayment   # activates/extends cover
    def settle_evening(self, day: date, gross_settlement_paise: Mapping[str, int], at: datetime) -> tuple[PremiumPayment, ...]

# chhatri/cases/service.py
class CaseService:
    def __init__(self, store: Store, audit: AuditLog, ids: IdFactory, rules: PolicyRules) -> None
    def open(self, *, kind: CaseKind, merchant_id: str, at: datetime, summary_en: str, summary_hi: str | None,
             evidence: Mapping[str, Any], claim_id: str | None = None, decision_id: str | None = None) -> Case
    def resolve(self, case_id: str, *, status: CaseStatus, by: str, resolution: str, at: datetime) -> Case
```

### 24.4 conversation

```python
# chhatri/conversation/service.py
class ClaimsPort(Protocol):            # implemented by the orchestrator; conversation never touches policy directly
    async def submit_personal_claim(self, merchant_id: str, slip: SlipExtraction, media_id: str) -> Decision
    async def open_dispute(self, merchant_id: str, text: str) -> Case
    async def quote_cover(self, merchant_id: str) -> tuple[CoverQuote, PremiumPayment | None]
    def latest_paid_decision(self, merchant_id: str) -> Decision | None
    def open_silence(self, merchant_id: str) -> date | None   # first silent day if a check-in is open

class ConversationService:
    def __init__(self, *, city: City, store: Store, audit: AuditLog, ids: IdFactory, clock: Clock, bus: EventBus,
                 channel: MessagingChannel, stt: SpeechToText, tts: TextToSpeech, chat: ChatModel | None,
                 slips: SlipReader, soundbox: Soundbox, claims: ClaimsPort, channel_name: Channel) -> None
    async def handle_text(self, merchant_id: str, text: str) -> tuple[Message, ...]       # inbound + replies
    async def handle_voice(self, merchant_id: str, audio: bytes, mime: str, *, transcript_hint: str | None = None) -> tuple[Message, ...]
    async def handle_image(self, merchant_id: str, image: bytes, mime: str, media_id: str) -> tuple[Message, ...]
    async def notify_area_payout(self, decision: Decision, payout: Payout, trigger: AreaTrigger) -> tuple[Message, ...]
    async def notify_instalment_paused(self, pause: InstalmentPause) -> Message
    async def notify_personal_paid(self, decision: Decision, payout: Payout) -> tuple[Message, ...]
    async def checkin_silent(self, merchant_id: str, first_silent_day: date) -> Message
    async def notify_officer_result(self, decision: Decision, case: Case) -> tuple[Message, ...]

# chhatri/conversation/intents.py
class Intent(StrEnum): WHY_AMOUNT, DISPUTE_AMOUNT, REPORT_ILLNESS, BUY_COVER, COVER_STATUS, GREETING, AFFIRM, DENY, UNKNOWN
def classify(text: str) -> Intent
# chhatri/conversation/messages.py
def render(key: str, lang: Literal["hi", "en"], **facts: object) -> str        # KeyError on unknown key / missing fact
def bilingual(key: str, **facts: object) -> tuple[str, str]                     # (hi, en)
# chhatri/conversation/guard.py
def grounded(reply: str, allowed_numbers: Iterable[str]) -> bool
```

### 24.5 integrations + workflows

```python
# chhatri/integrations/registry.py
@dataclass(frozen=True, slots=True)
class Integrations:
    stt: SpeechToText; tts: TextToSpeech; chat: ChatModel | None; slips: SlipReader
    channel: MessagingChannel; payments: PaymentLinks; weather: WeatherFeed
    workflows: WorkflowEngine; memory: MemoryGraph; soundbox: Soundbox
    statuses: tuple[IntegrationStatus, ...]
def build_integrations(settings: Settings, *, scheduler: "Scheduler", step_handlers: "StepHandlers", data_dir: Path) -> Integrations

# chhatri/workflows/definitions.py
WORKFLOWS: Mapping[str, tuple[StepSpec, ...]]
@dataclass(frozen=True, slots=True)
class StepSpec: name: str; delay_minutes_from_start: int   # sim-time offsets; payout: execute_payout 0, credit 4, pause 5, notify 4
class Scheduler(Protocol):
    def schedule(self, at: datetime, name: str, fn: Callable[[], Awaitable[None]]) -> None
    def now(self) -> datetime
class StepHandlers(Protocol):          # implemented by the orchestrator
    async def run_step(self, workflow: str, step: str, payload: Mapping[str, Any]) -> None

# chhatri/workflows/runner.py
class InProcessWorkflowEngine:         # implements WorkflowEngine; schedules steps via Scheduler at start + delay
class N8nWorkflowEngine:               # POST {N8N_BASE_URL}/webhook/chhatri-{workflow}; n8n calls /internal/workflows/{step}
```

### 24.6 replay (integration core) + api

```python
# chhatri/replay/state.py
@dataclass(frozen=True, slots=True)
class StaticContext:                       # built once per process (load_static)
    settings: Settings; rules: PolicyRules; data_dir: Path; artifacts_dir: Path
    calibration: Calibration; city: City
    model: ExpectedSalesModel | None; model_error: str | None     # None + error when artefacts missing
    zones_geojson: dict; hexes_geojson: dict
    backtest_report: dict | None; premiums: Mapping[str, int]
def load_static(settings: Settings) -> StaticContext

class Runtime:                             # one per loaded scenario (SPEC §3: ids/store/audit reset on load)
    scenario: Scenario; clock: ManualClock; ids: IdFactory; store: Store; audit: AuditLog
    bus: EventBus                          # the process-wide bus (shared across loads)
    shocks: ShockCalendar; history: SalesPanel     # history_start .. scenario.day+1 (full days)
    expected: np.ndarray                   # (M, 24 * scenario days, 3) predictions for the scenario day(s)
    integrations: Integrations; conversation: ConversationService; orchestrator: "Orchestrator"
    engine: "ReplayEngine"; scheduler: "SimScheduler"
    payouts: PayoutService; instalments: InstalmentService; premiums: PremiumService; cases: CaseService

class AppState:                            # stored at FastAPI app.state.chhatri
    static: StaticContext; bus: EventBus
    @property
    def runtime(self) -> Runtime           # RuntimeError when nothing is loaded
    async def load(self, scenario: str) -> Runtime       # publishes `scenario`; ValueError on unknown name
    async def shutdown(self) -> None
    def preflight(self) -> list[dict]      # [{name, ok, detail}] — SPEC §19 /api/preflight

# chhatri/replay/scheduler.py
class SimScheduler:                        # implements workflows.Scheduler on simulated time
    def schedule(self, at: datetime, name: str, fn: Callable[[], Awaitable[None]]) -> None
    def now(self) -> datetime
    async def run_due(self, now: datetime) -> int          # runs every job with at <= now in (at, seq) order
    def pending(self) -> int

# chhatri/replay/engine.py
class ReplayEngine:
    async def play(self, speed: float | None = None) -> None      # speed = sim minutes per real second (1..120)
    async def pause(self) -> None
    async def step(self, minutes: int) -> None                    # synchronous advance, awaits all effects
    async def seek(self, hhmm: str) -> None                       # forward: step; backward: AppState reload + step
    @property
    def running(self) -> bool
    @property
    def speed(self) -> float

# chhatri/replay/orchestrator.py  — implements ClaimsPort (§24.4) and StepHandlers (§24.5)
class Orchestrator:
    async def on_minute(self, at: datetime) -> None               # scheduled scenario hooks (e.g. 11:20 check-in)
    async def on_hour(self, at: datetime) -> None                 # detection -> claims -> decisions -> workflows
    async def run_step(self, workflow: str, step: str, payload: Mapping[str, Any]) -> None
    async def handle_callback(self, run_id: str, workflow: str, step: str, payload: Mapping[str, Any]) -> dict
                                                                  # n8n: schedules the effect at decision time + offset; idempotent per (run_id, step)
    async def officer_decide(self, case_id: str, *, approve: bool, officer_id: str, note: str) -> Decision
    async def paytm_paid(self, link_id: str, txn_id: str | None) -> PremiumPayment
    # + ClaimsPort methods: submit_personal_claim, open_dispute, quote_cover, latest_paid_decision, open_silence

# chhatri/replay/views.py — the ONLY place domain objects become §19.2 JSON (dicts with *_label strings)
def clock_view(rt: Runtime) -> dict                     # ClockState
def zone_snapshot(rt: Runtime, zone_id: str) -> dict    # ZoneSnapshot
def kpis_view(rt: Runtime) -> dict                      # Kpis
def snapshot(rt: Runtime) -> dict                       # StateSnapshot
def zone_panel(rt: Runtime, zone_id: str) -> dict       # ZonePanel (exact §17.2 strings)
def alert_view(a: Alert) -> dict; def trigger_view(t: AreaTrigger) -> dict
def decision_view(d: Decision) -> dict; def payout_view(p: Payout) -> dict; def pause_view(p: InstalmentPause) -> dict
def merchant_summary(rt: Runtime, merchant_id: str) -> dict; def merchant_detail(rt: Runtime, merchant_id: str) -> dict
def message_view(m: Message) -> dict; def case_view(rt: Runtime, c: Case) -> dict; def audit_view(e: AuditEntry) -> dict
def policy_view(rules: PolicyRules) -> dict; def integrations_view(statuses: Sequence[IntegrationStatus]) -> list[dict]
```

`chhatri/api/` is thin: `create_app(settings: Settings | None = None, *, state: AppState | None = None) ->
FastAPI` (lifespan: `load_static`, `AppState.load("monsoon")` paused at the scenario start); routers
translate HTTP ⇄ AppState/Runtime calls and wrap `views` output in the §19 envelope; `security.py`
(officer bearer, internal secret, WhatsApp signature, rate limiting, upload validation by magic
bytes); `sse.py` (sse-starlette `EventSourceResponse`, `ping=15`, resumes after `Last-Event-ID`).
