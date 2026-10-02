# 0002: Area sales index trigger

| | |
|---|---|
| Status | Accepted |
| Owner | Ujjwal Pardeshi |
| Date | 2026-10-02 |
| Related | [SPEC §4](../../SPEC.md) · [SPEC §9.6](../../SPEC.md) · [DEMO.md](../../DEMO.md) · [Facts and sources (A8, A14)](../../01-strategy/facts-and-sources.md) |

## TL;DR

The trigger for area income cover combines three signals: a zone's **hourly sales index** (actual ÷ expected, from live Paytm data and a LightGBM model) below **50% for 3 consecutive hours**, **below the model's conformal lower bound**, and **during a red or orange weather alert**. At least 20 shops in the zone must be in the index. This replaces weather-only triggers (basis-risk problem, A8) and individual-shop logic (collusion risk). It measures loss from the merchant's own data.

## Context

**Basis risk:** parametric income cover for gig workers and SMEs exists (Riskwolf, SEWA, A14); it triggers on weather or area-level proxies. Clarke et al. (2012, A8) found a one-in-three chance of no payout even when area-average yield was totally lost. Chhatri's trigger is designed to reduce this gap: instead of weather alone, it watches **the merchant's actual sales during the alert** and compares them to an expected baseline.

**Why not individual shop triggers?** A merchant can claim a loss by simply not using the terminal for a day. An area-level index means one shop cannot fake a loss; it must match the zone's pattern.

**Model calibration:** the expected-sales model (LightGBM, quantile regression) predicts p10, p50, p90 for each shop on each day. The trigger uses p50 as the baseline and the conformal lower bound (approximately p10 in backtest) as the floor. Simulated sales (driven by real rainfall, 2024–2025) are used to train and backtest (facts-and-sources.md §D, circular calibration disclosed openly); post-launch, the model will be retrained with production merchant data.

## Decision

**Trigger logic** (backend/chhatri/detect/triggers.py, rules.yaml, K1):

1. Every hour, calculate the zone's **area sales index** = Σ(actual sales in shops with recent activity) ÷ Σ(expected sales on that hour).
2. Check three conditions in parallel for the **last 3 consecutive hours**:
   - Index < 50%.
   - Index < model's conformal lower bound (p10 estimate, approx.).
   - A red or orange alert covers the zone (from Open-Meteo, cached or live).
3. All three must be true for at least one "window" of 3 consecutive hours.
4. At least **20 shops** must be in the index (to prevent small-zone noise).
5. If triggered, an area claim is created; the policy engine (`evaluate_area_claim`) decides approval for each covered shop.

**Payout logic** (rules.yaml):

- Amount = 0.5 × expected_day × (1 − index%), capped at ₹2,500 per shop per day.
- Example (demo): zone Z7, index 37%, expected ₹4,380/day → 0.5 × ₹4,380 × 63% = ₹1,380.

**Conformal bound:** the model's lower quantile (p10) is used as a threshold to avoid false triggers on volatility.

## Alternatives considered

1. **Weather-only trigger (rejected):** Red alert → automatic area payout. Pro: simple; no sales data dependency. Con: basis risk (A8); many false positives; merchants uninsured on non-rainy days.

2. **Individual-shop sales drops (rejected):** Any shop with sales below 40% of expected is paid. Pro: personalised. Con: a merchant can fake it by not selling; no area signal; higher claim count and moral hazard.

3. **Hybrid with late-alert check (considered):** Trigger on sales, then verify alert was issued ≥12 hours before the drop (to rule out false alerts). Con: adds latency; makes the alert a legal prerequisite; more rigid.

## Consequences

**Positive:**

- **Basis-risk reduction:** the trigger watches actual sales, not weather proxies, so it matches loss to cover more often (backtest: 60% of real drops paid vs 33% for weather-only; A8).
- **Area-level immunity:** one merchant's absence does not trigger a payout; the whole zone must show a loss.
- **Model grounding:** the expected-sales model can be retrained with real data post-launch (roadmap).
- **Transparent:** the formula, threshold and data sources are audited and explained to merchants (K5).

**Negative:**

- **Complexity:** three conditions and a lookback window add code and test surface.
- **Model dependency:** the trigger relies on expected-sales predictions; a bad model = bad trigger. Mitigate with evals and post-launch monitoring (roadmap).
- **Simulated training data:** current model is trained on simulated sales (facts-and-sources.md §D); post-launch, the model can be retrained with real merchant sales data for improvement (roadmap).

**Risks:**

- **Circular calibration:** simulation parameters are tuned to reproduce the demo's numbers; this is not evidence of real performance. Mitigated by saying so openly (see the errata in [current-state-audit.md](../../01-strategy/current-state-audit.md)).
- **Threshold gaming:** once merchants know the 50% threshold, they may manage sales around it. Mitigate by not publicizing exact thresholds; auditing sales patterns; working with a compliance team post-launch.
- **Alert timing:** if an alert is issued late (e.g., after the sales drop), the trigger will not fire. Mitigate with a 72-hour look-ahead during cover purchase (K6); a future roadmap could use forecasted alerts.

## How we will know it was right

**Signals:**

1. Backtest shows the trigger pays simulated drops more often than weather-only (specification validation shows 60% vs 33%, fact D).
2. No zone's conformal bound is violated (model recalibration catches drift).
3. Merchants can reproduce the ₹1,380 payout from the demo's index (37%), expected (₹4,380) and formula (facts-and-sources.md, section D).
4. The trigger fires deterministically on the same scenario seed; no randomness in alert matching or index calculation.
5. A partner insurer accepts the trigger as meeting the basis-risk criterion in product underwriting.

## Follow-ups

- **Task:** Post-launch, train the model on production merchant sales data (roadmap).
- **Task:** Implement alert look-ahead enforcement during cover purchase (K6, X7 test).
- **Task:** Monitor false positive and false negative rates in the pilot and adjust the 50% threshold.

## Open questions

1. Does the partner insurer require the conformal bound to be formally validated (e.g., with a coverage test), or is p10 a sufficient proxy? Owner: Ujjwal Pardeshi.
2. Should the trigger consider seasonal sales patterns (e.g., festival spikes) or stick to daily baselines? Owner: Ujjwal Pardeshi.

## Changelog

- 2026-10-02 · v2 · final consistency pass against the code: no changes needed; ADR correctly describes the area sales index trigger and its backtest validation.
- 2026-10-02 · v1.1 · fact-check pass: clarified that sales data is simulated for demo; reframed backtest results as specification validation; disclosed circular calibration openly; noted post-launch model retraining with production data.
- 2026-10-02 · v1 · first draft.
