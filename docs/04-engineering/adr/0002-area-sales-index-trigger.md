# 0002: Area sales index trigger

| | |
|---|---|
| Status | Accepted |
| Owner | Ujjwal Pardeshi |
| Date | 2026-10-02 |
| Related | [SPEC §4.3, §6.3, §6.4, §7.4, §8, §18](../../SPEC.md) · [fs-01 area auto-claim](../../02-product/feature-specs/fs-01-area-auto-claim.md) · [fs-08 console (what-if panel)](../../02-product/feature-specs/fs-08-claims-officer-console.md) · [ML model card](../ml-model-card.md) · [Backtest report](../../../backend/artifacts/backtest/report.md) · [DEMO.md](../../DEMO.md) · [Facts and sources (A8, A14, D)](../../01-strategy/facts-and-sources.md) |

## TL;DR

An area claim starts when a **zone**, not a shop, shows a sales collapse that an alert explains. At every hour boundary the detector checks each zone and fires when all of these hold:

- a RAIN or CIVIC alert, already issued, is valid for the whole 3-hour window;
- each of the 3 hourly sales indices (actual ÷ expected) is below 50%;
- the 3-hour window index is below the zone's **conformal lower bound**;
- at least 20 covered shops are in the index;
- the zone has not fired already that day.

Expected sales come from a LightGBM quantile model. This keeps the idea behind the weather-index literature (A8) and replaces a weather-only trigger with the merchants' own sales. **Every sale, every alert and every "real drop" in the backtest is simulated, and the calibration is circular by design** (section "Honest limits"). The decision is about the shape of the rule. It does not claim the rule has been measured on real merchants.

## Context

**Basis risk.** Weather-index insurance can fail to pay when the loss is real. Clarke et al. (2012, A8) studied 270 weather-index crop products and found roughly a one-in-three chance of no payout even when the area-average yield was totally lost. Parametric income cover for gig workers, farmers and small businesses already exists (Riskwolf, A14, with an Indian subsidiary since 2024). Chhatri's idea is to watch the merchants' own sales inside the payments app, during an alert, instead of the weather alone.

**Why a zone, not a shop.** A shop can show a "loss" by not using its terminal. One shop cannot move a zone's index, and the 20-shop quorum stops a thin zone from firing on noise.

**Why three conditions.** The alert says what caused the drop, and keeps ordinary slow days out (Z9 on the demo day: 61% with no alert, no payout, by design). The 50% floor sets the size of the drop. The lower bound says the drop is outside normal volatility for that zone.

**The model.** Three LightGBM boosters, one per quantile (P10, P50, P90), predict each shop's expected sales for each hour. Zone and shop type are features, with the hour, weekday, festival flag, month, the shop's trailing normal-week level and its usual share of the day in that hour. Training uses normal days only: days with an alert, bandh days and closure days are left out (SPEC §7.1, §7.2). The trigger uses P50 as "expected". The zone lower bound is not a P10. It is the ⌊(n+1)·0.025⌋-th smallest 3-hour window index (1-based, an integer percent, half up) over the held-out normal zone-days, a one-sided 2.5% conformal rank (`backend/chhatri/forecast/calibrate.py`, SPEC §7.4). With fewer than 39 windows the rank is 0, so no bound can be certified, the stored bound is 0%, and no trigger can fire in that zone. The bounds are stored per zone in `backend/artifacts/model/manifest.json` (`lower_bound_pct`: Z3 89, Z7 92, Z9 90, Z12 78 on the demo day; across all 24 zones they run from 47 to 94).

## Decision

**Trigger rule** (`backend/chhatri/detect/triggers.py`, `evaluate_hour`; values in `backend/chhatri/policy/rules.yaml`, version `pilot-0.1`). At hour boundary t the window is [t − 3 h, t). All comparisons are strictly less than.

| Condition | Rule | Source of the value |
|---|---|---|
| Alert | A RAIN or CIVIC alert for the zone, issued by t, is valid for the whole window. The alert's kind matters, its level (YELLOW, ORANGE, RED) does not | `TRIGGER_ALERT_KINDS` in `triggers.py` |
| Floor | Each of the 3 hourly indices is below 50 | `area.index_floor_pct` |
| Bound | The 3-hour window index is below the zone's lower bound | `manifest.json` |
| Quorum | At least 20 shops are in the index | `area.min_shops_in_index` |
| Once a day | The zone has not triggered for that day | `already_triggered` set of (zone, day) |

**The index** is Σ actual ÷ Σ expected over the zone's covered merchants (those with a cover) that are scheduled open in at least one hour of the window, as an integer percent, half up. Merchants who closed that day stay in the index, exactly as at calibration time, so calibration and detection scores are exchangeable (`backend/chhatri/detect/area_index.py`, `backend/chhatri/forecast/calibrate.py`).

**What a trigger is.** An `AreaTrigger` record with the hourly indices, the window index, the bound, the shop count and the alert id. It is not a payment. Each covered shop's claim is then decided by the policy engine (`evaluate_area_claim`, nine HARD checks, [fs-01](../../02-product/feature-specs/fs-01-area-auto-claim.md)). Per shop the payout is ½ × the published expected day × the drop %, rounded to the rupee and capped at ₹2,500, where drop % = 100 − window index (`backend/chhatri/policy/amounts.py`, `area_breakdown`).

**Demo day (monsoon, Tue 19 Aug 2025).** Z7 has hourly indices 35, 39 and 37, window 37 (below its bound 92), 46 shops and alert `A-20250818-01`, so it fires with a 63% drop. Anil (S-0142) has an expected Tuesday of ₹4,380, so ½ × ₹4,380 × 63% = ₹1,380. Z3 (window 38, bound 89, 141 shops) and Z12 (47, bound 78, 125 shops) fire too. Z9 (window 61, no alert) shows `slow_day`.

**Zone statuses** the map shows: `triggered`, `no_data`, `watch`, `slow_day`, `normal` (rules in the `triggers.py` docstring).

**Guards outside the trigger.** The shop's cover must have been bought before the alert was issued (`COVER_BEFORE_ALERT`) and its premium prepaid (`PREMIUM_PREPAID`), both HARD checks in the policy engine. A new cover always starts after the 7-day waiting period, and a quote taken while an alert is valid, or issued and starting within 72 hours (`cover.alert_lookahead_hours`), is marked BLOCKED for an immediate start (SPEC §9.5).

**One rule, several readers (PLANNED).** Wave 1 extracts the conditions into a pure `trigger_verdict` ([fs-09](../../02-product/feature-specs/fs-09-policy-engine-and-audit.md) section 9.5) that the detector, the H14 counterfactual and the what-if panel (fs-08, `POST /api/whatif/area`) all call, so no threshold is copied.

## Alternatives considered

1. **Weather-only trigger (rejected).** An alert or a rain total pays every shop of the zone. It is simple and needs no sales data. It carries the basis risk of A8, and in the simulated backtest it paid 287 of 336 payouts with no real drop (85%) and could not see non-rain shocks.
2. **Individual-shop sales drop (rejected).** Any shop below some share of expected sales is paid. A shop can fake it, there is no area signal, and it has no quorum.
3. **Sales-only trigger with no alert (rejected).** Slow days would pay. A slow day is not a loss event the product covers, so the alert is part of the rule.
4. **Minimum alert lead time (considered, not built).** Require the alert to be issued some time before the drop, so an alert issued after the loss cannot trigger. It would make the alert's timing a prerequisite and is not in `rules.yaml`. The built rule needs the alert issued by the evaluation time and valid for the whole window. The 72-hour look-ahead applies to cover purchase, not to the trigger.

## Consequences

**Positive**

- One shop cannot fake a zone's index, and a thin zone cannot fire.
- Each condition is a number a merchant or judge can read. The explanation and the Z9 note show them today, and the receipt and the what-if panel (both PLANNED) will too.
- Deterministic: the same seed gives the same triggers and ids (`backend/tests/replay/test_determinism.py`, the 21 tests of `backend/tests/detect/test_triggers.py`).

**Negative**

- Model dependency: a poor expected-sales model gives a poor trigger. The serving model's held-out P10–P90 band covers 78.2% of cells against 80% nominal (`coverage_p10_p90` in `manifest.json`), measured on simulated days.
- The thresholds are published, on the Policy page and the map legend, and the what-if panel (PLANNED) will show them too. Gaming is limited by the zone-level index, the quorum and the per-shop checks, not by secrecy.
- A zone whose bound is at or below the 50% floor is governed by the bound, and a zone with too few calibration windows cannot fire at all.

**Risks**

- **Circular calibration** (next section).
- **Alert timing.** Alerts in the simulation come from a perfect forecast. A real feed is later and noisier, and an alert issued after the drop would not trigger.
- **Alert level.** Policy wording C2 says "Red alert". The code accepts a RAIN or CIVIC alert of any level. Wording and rule need aligning with the insurer.

## Honest limits

The numbers below are why the backtest is "specification validation on simulated sales and real rainfall" and nothing stronger.

1. **The demo day is scripted and tuned.** `backend/chhatri/pipeline/day_search.py` scales the scripted storm so the 14:00 to 17:00 window index is exactly 37, 38 and 47% in Z7, Z3 and Z12, and makes Z9 show 61% on its slow day. The demo numbers show the engine's arithmetic. They are not a finding. The tuning knobs are in `backend/artifacts/calibration.json`.
2. **The "real drops" are the simulator's own shocks.** Sales come from `backend/chhatri/sim/sales.py` driven by real Open-Meteo rainfall. The shocks are defined in `sim/disruptions.py`: rain impact, fictional city-wide bandhs on 10 Sep 2024 and 9 Sep 2025 (sales down 75% all day), and slow days (1.5% of zone-days, down 25% to 45%, only without an alert). A real drop is a zone-day whose loss against the simulator's own no-shock sales (`sim/truth.py`) is at least 40% (`REAL_DROP_LOSS` in `backend/chhatri/backtest/config.py`). The backtest's 148 real drops are 50 rain, 48 bandh and 50 slow-day zone-days.
3. **Alerts are simulated with a perfect forecast.** ORANGE from 30 mm and RED from 60 mm of trailing 3-hour rain, issued 60 minutes ahead; civic alerts issued at 19:00 the evening before a bandh (`sim/alerts.py`).
4. **The bound is calibrated on simulated normal days.** Its 97.5% statement holds inside the simulator only.
5. **The headline mixes causes.** Chhatri paid 89 of 148 real drops (60%) against 49 of 148 (33%) for weather-only. On the 50 rain drops weather-only paid 47 and Chhatri paid 41. Chhatri's total comes from the 48 bandh drops, which a rain trigger cannot see (it paid all 48, weather-only paid none), and from paying less when nothing happened (36 of 125 payouts without a real drop, against 287 of 336). The 50 slow-day drops count as misses for Chhatri by design, because a slow day with no alert is not a loss event the cover pays.
6. **Premiums use the same losses.** They are priced as expected loss ÷ (1 − 0.35) from the simulated losses they are then compared with, so each zone's loss ratio is about 65% by construction and in-sample.

What the backtest does show is that the rule pays when its conditions hold and not otherwise, and what each candidate rule would have paid in this simulated world. The console's Backtest page is to carry a caveat line to the same effect (fs-08 section 13.3).

## How we will know it was right

1. The same seed gives the same triggers, ids and audit hashes (`test_two_independent_monsoon_replays_to_the_end_are_identical`).
2. A merchant can rebuild ₹1,380 from the numbers shown: 63% drop, ₹4,380 expected day, half (`test_anil_is_paid_1380_with_the_spec_explanation` and `test_trigger_numbers` in `backend/tests/test_golden_numbers.py`; `scripts/tests/test_docs.py` pins the same strings in DEMO.md).
3. A shadow phase in a pilot: run the rule on real merchant sales and a real alert feed before any money moves, and compare it with the losses merchants report.
4. The bound is re-fitted on real normal days and checked for coverage on held-out real windows.
5. A partner insurer accepts the trigger against its own basis-risk criterion.

## Follow-ups

- Extract `trigger_verdict` (wave 1) and use it in the what-if panel (wave 4).
- Add the caveat line to the Backtest page (wave 4, fs-08).
- Align the alert-level wording (C2) with the rule, with the insurer.
- Pilot: shadow phase, then refit the model and the bounds on real data.

## Open questions

1. Does the partner insurer require the bound to be validated with a formal coverage test, or is the conformal rank enough? Owner: Ujjwal Pardeshi.
2. Should the trigger model seasonal spikes (the simulator has a Ganesh Chaturthi uplift) or stay with the daily baseline? Owner: Ujjwal Pardeshi.
3. Should the rule require "Red alert" as C2 says, or any alert level as built? Owner: Omkar Kadam, with the insurer.

## Changelog

- 2026-10-02 · v3 · circular calibration spelled out (scripted demo day, simulator-defined real drops, perfect-forecast alerts, same-simulator bound, mixed-cause headline); conformal bound described as the 2.5% rank, not P10; alert is any RAIN or CIVIC level; index over covered scheduled-open shops; sales and alerts are simulated (only the rainfall is the real Open-Meteo record); the "do not publish thresholds" mitigation is removed; real file paths and test names
- 2026-10-02 · v2 · final consistency pass against the code: no changes needed; ADR correctly describes the area sales index trigger and its backtest validation.
- 2026-10-02 · v1.1 · fact-check pass: clarified that sales data is simulated for demo; reframed backtest results as specification validation; disclosed circular calibration openly; noted post-launch model retraining with production data.
- 2026-10-02 · v1 · first draft.
