# ML Model Card: Expected-Sales Quantile Regression

| | |
|---|---|
| Status | Draft v1 · 2 Oct 2026 |
| Owner | Ujjwal Pardeshi |
| Audience | Technical: ML engineers, data scientists, compliance · Non-technical: insurers' actuaries, regulators |
| Related | [Backtest report](../../backend/artifacts/backtest/report.md) · [Facts and sources](../01-strategy/facts-and-sources.md) · [Current-state audit](../01-strategy/current-state-audit.md) · [Policy engine and audit](../02-product/feature-specs/fs-09-policy-engine-and-audit.md) |

## TL;DR

- **Model:** Three LightGBM quantile regressors (P10, P50, P90) predict expected hourly shop sales per zone and shop type.
- **Training data:** Simulated (LIVE label: SIMULATED) sales driven by real Open-Meteo rainfall (Jun–Sep 2024 and Jun–Sep 2025), fit on Feb–Aug 2025, excluding alert days and zero-transaction days.
- **Purpose:** The P50 estimate and conformal lower bound (P10 range, 97.5th percentile) feed the area-index trigger (K1), not individual credit decisions.
- **Honest framing:** The backtest is "specification validation on simulated sales and real rainfall". The calibration is circular by design: simulation parameters are searched to match the demo numbers. Do not claim the backtest shows what the model will do on real merchants.
- **Real data path:** For a real pilot, the model would be refitted on merchant sales logs and weather. Conformal calibration would use a held-out interval.

## 1. Model details

### Architecture

- **Framework:** LightGBM 4.7.0, three separate boosters (one per quantile)
- **Quantiles:** P10 (0.10), P50 (0.50), P90 (0.90)
- **Target:** Expected daily sales per merchant per hour (paise), normalized by the merchant's level (log median sales on normal days)
- **Hyperparameters (from `backend/chhatri/forecast/training.py`):
  - Boost rounds: 200
  - Learning rate: 0.05
  - Num leaves: 31
  - Min data in leaf: 100
  - Minimum training rows (fit): 1,000
  - Threads: 1 (deterministic; `LightGBM/OpenMP default = 0` in production)
- **Persistence:** Text format (`.txt`), one per quantile in `backend/artifacts/model/` (p10.txt, p50.txt, p90.txt)

### Conformal calibration

- **Method:** Held-out (calibration) weeks are never fitted; metrics are computed on them (SPEC §7.4).
- **Conformal lower bound per zone:** For each zone, the 2.5th percentile of 3-hour-window area indices across held-out normal zone-days, expressed as an integer percent (half-up).
- **Rank formula:** floor((n+1) × 0.025) where n = count of 3-hour windows (SPEC §7.4).
- **Stored bounds:** `backend/artifacts/model/manifest.json`, field `lower_bound_pct` per zone. Examples: Z7 92%, Z3 89%, Z9 90%.
- **Purpose:** The area index must fall below both 50% AND below the zone's lower bound to fire the trigger (K1).

### Model versions and artifacts

- **Manifest:** `backend/artifacts/MANIFEST.json` (SHA-256 hashes of all artifacts)
- **Model files:** 
  - `backend/artifacts/model/p10.txt`, `p50.txt`, `p90.txt` (LightGBM boosters)
  - `backend/artifacts/model/schema.json` (fixed category lists for zones and shop types)
  - `backend/artifacts/model/manifest.json` (lower bounds, pinball losses, coverage, metadata)
  - `backend/artifacts/model/training.json` (full training metadata: window dates, row counts, seed)
- **Calibration parameters:** `backend/artifacts/calibration.json` (simulation tuning knobs, filled at artifact-build time)
- **Version pinning:** Seed 20251019 locks the random state; dataset versions (h3, numpy, pandas, lightgbm, python) are pinned in `model/training.json`

## 2. Intended use

### Primary use case

**Area-index trigger (K1).** The model supplies the expected P50 sales per zone-hour, used to compute the area index (actual ÷ expected). The conformal lower bound is a zone-specific threshold: the trigger fires when the index is below 50% AND below the zone's lower-bound percentile, during an active alert, for 3 consecutive hours, with at least 20 shops in the index.

### Supporting use cases

- **Expected-day calculation:** The daily expected sales cap ₹2,500 per shop (K1) is 50% of the P50 of a shop's expected sales on the most-comparable past normal day, not the model's prediction.
- **Premium pricing:** Zone-specific premiums derive from the backtest loss ratio (insurance arithmetic, not the model prediction).

### Role in claim decisions

- The model **does not** decide whether a claim is paid. The policy engine (`backend/chhatri/policy/rules.yaml`, version pilot-0.1) is the only authority.
- The model is **not** used for individual credit decisions, underwriting, or pricing (per-shop or per-merchant).

## 3. Out-of-scope uses

- **Individual credit scoring:** Do not use this model to assess credit risk for a single merchant.
- **Underwriting decisions:** Do not use zone or merchant projections to set insurance terms or refuse cover.
- **Claim-level pricing:** Do not use the model to price individual hospital-cash claims or set caps per merchant.
- **Operational decisions:** Do not override the policy engine's decision based on the model's prediction.

## 4. Training data

### Data source

**SIMULATED:** Sales are generated by `backend/sim/sales.py` driven by real rainfall. The simulator is labelled and must not be presented as merchant data on stage.

- **Real rainfall:** Open-Meteo historical data (https://archive-api.open-meteo.com/) for Colaba and Santacruz, Mumbai, Jun–Sep 2024 and Jun–Sep 2025.
- **Rainfall events:** The simulator samples from recorded rainfall patterns; an "alert" occurs when rainfall reaches the threshold (e.g., 64.5 mm, IMD "heavy" classification).
- **Merchant count:** 1,821 simulated shops across 24 Mumbai zones, each with a fixed `ShopType` (KIOSK, SMALL, MEDIUM, LARGE). One shop is marked uninsured (not in the payout).

### Training window

- **Training window:** 18 Feb 2025 – 18 Aug 2025 (fit period, excluding calibration weeks)
- **Calibration window:** 22 Jul 2025 – 18 Aug 2025 (4 weeks, held out during fitting)
- **Rows (fit):** 1,315,791
- **Rows (calibration):** 687,733
- **Exclusions (SPEC §7.2):** 
  - Zone-days on which any alert is in force (no training on alert days)
  - Merchant-days with zero transactions
  - Shop-hours outside business hours (09:00–21:00 IST)
  - Rows from merchants with no "normal day" baseline (needed to compute level)

### Seed and reproducibility

- **Random seed:** 20251019 (pinned in `backend/artifacts/model/training.json`)
- **Dependencies locked:** Python 3.12.3, pandas 3.0.6, numpy 2.5.3, lightgbm 4.7.0, h3 4.5.0, shapely 2.1.2
- **Determinism:** Reproducible from the same seed and rainfall data.

### Feature engineering

**Categorical features (fixed categories, persisted with model):**
- `zone_id`: 24 Mumbai zones (Z1–Z24)
- `shop_type`: KIOSK, SMALL, MEDIUM, LARGE (enum, `backend/chhatri/domain/enums.py`)

**Numeric features:**
- `hour`: 0–23 (hour of day, IST)
- `dow`: 0–6 (day of week; 0 = Monday)
- `is_festival`: binary, 1 during Ganesh Chaturthi (10-day window; SPEC §6.3)
- `month`: 1–12 (calendar month)
- `shop_level`: log(median normal-day sales per hour), captured from history before the row's date
- `shop_hour_share`: estimated sales share in that hour within the day (from `backend/chhatri/forecast/history.py`)

**Target:** `amount / level`, normalized sales per shop-hour.

See `backend/chhatri/forecast/features.py` and `backend/chhatri/forecast/history.py`.

## 5. Evaluation metrics

### Held-out metrics (calibration set, SPEC §7.4)

From `backend/artifacts/model/manifest.json`:

| Metric | P10 | P50 | P90 |
|---|---|---|---|
| **Pinball loss** | 2,372.75 | 5,314.37 | 2,618.38 |
| **Coverage (P10–P90)** | 78.2% | — | — |

**Interpretation:** The interval [P10, P90] covers 78.2% of held-out values, a proxy for calibration quality. Pinball loss is a quantile-specific error measure (lower is better).

### Conformal lower bound (97.5th percentile)

Per-zone lower bounds (integer %), stored in `backend/artifacts/model/manifest.json`, `lower_bound_pct`:
- Z7: 92%, Z3: 89%, Z9: 90%, Z12: 78% (other zones in the manifest)

Computed as: the 2.5th percentile of area-index values across 3-hour windows in held-out normal zone-days.

### Backtest metrics (simulated sales, real rainfall)

From `backend/artifacts/backtest/report.md`:

| Measure | Chhatri | Weather-only |
|---|---|---|
| Real sales drops paid | 89 / 148 (60%) | 49 / 148 (33%) |
| False positives (payouts with no drop) | 36 / 125 (29%) | 287 / 336 (85%) |
| Trigger to money | same day, 4 min | next day |
| Total paid | ₹1,49,40,252 | ₹3,36,08,953 |
| Personal claims → human | 359 / 844 (43%) | — |

**What this shows:** The trigger is faster and has fewer false positives than a weather-only baseline. Personal claims (hospital-cash, K2) behave similarly across zones.

**What this does NOT show:** Actual merchant response, actual loss causation, or real basis risk. The simulator defines a "real drop" as ≥40% loss of expected sales; a merchant's loss profile may differ.

## 6. Circular calibration (honest framing)

### Why it was done

To validate that the demo scenario's numbers (Z7 37%, Anil's ₹4,380 expected day, ₹58,900 total for Z7) can be reproduced deterministically, the simulation parameters and premium loadings are searched (`backend/chhatri/pipeline/targets.py`, `day_search.py`, `level_search.py`) to match the demo numbers.

### What happens

1. Simulation parameters (rainfall scale per zone, merchant base-day sales, loss patterns) are tuned.
2. LightGBM models are trained on simulated sales driven by real rainfall.
3. Premiums are set so that every zone's backtest loss ratio = expected loss ÷ (1 − 0.35) ≈ 65% by construction.
4. The replay produces the exact demo numbers on every scenario load (SPEC §23, §24.1).

### What it means

- The system is deterministic and reproducible.
- The policy engine and audit log work correctly.
- The backtest does **not** show how the model will perform on real merchants.
- The 65% loss ratio is **not** an estimate of real merchant loss; it is a design choice.
- Do **not** cite the backtest as evidence for pricing, actuarial assumptions or risk assessment in a real pilot.

### Real data path

For a live pilot:
1. Collect real merchant sales logs and real rainfall (Open-Meteo or a local weather API).
2. Fit the model on real history with standard train-test-calibration splits (no circular search).
3. Measure real hold-out metrics.
4. Derive zone-specific loss ratios from real claims data, with an actuary's sign-off.
5. Re-price premiums and re-calibrate bounds.

## 7. Limitations and risks

### Data limitations

- **Simulated merchant behavior:** No real merchant response to claims, disputes, renewals or attrition.
- **Limited weather patterns:** Only 4 months of real rainfall per year; extreme events may be underrepresented.
- **Zone heterogeneity:** Zones are H3 cells; a real merchant's true risk depends on micro-location (street, building type, goods) not captured here.
- **New shops:** The model requires a "level" (baseline sales) computed from history. A shop with <7 days of history is excluded from training and may behave unpredictably at run time.

### Model limitations

- **Quantile regression vs classification:** The model predicts sales magnitude, not whether a drop will occur. A merchant could lose a large share of sales without hitting the 50% threshold (basis risk, A8).
- **Feature simplicity:** Only zone, shop type, hour, day, festival, and history-based level. Unmeasured factors (merchant behavior, local events, supply-chain shocks) are not captured.
- **Fixed thresholds:** The 50% index floor and per-zone conformal bounds are static. A drift in merchant behaviour or rainfall patterns will not trigger automatic retraining.

### Operational risks

- **Slow retraining:** The model is rebuilt manually via `make data`, not on a live schedule. Drift is detected offline, if at all.
- **Conformal bound edge case:** If a zone has <39 held-out 3-hour windows, the finite-sample quantile is undefined, and the bound is set to 0% (no trigger fires in that zone). The logs emit a warning.
- **Missing zones in rules:** If `backend/chhatri/policy/rules.yaml` (version pilot-0.1) references a zone not in the model, payouts may fail silently (X3 guard to be added).

## 8. Fairness considerations

### By shop type

The model treats all shop types (KIOSK, SMALL, MEDIUM, LARGE) as a feature. Shops of the same type in the same zone are held to the same expected-sales distribution. Smaller shops may have noisier sales, raising the risk of false positives (a slow day is not a loss event).

### By zone

Each zone has its own conformal lower bound, acknowledging geography. However, within-zone variation (microclimate, street layout, competition) is invisible to the model.

### By merchant tenure

The model requires ≥7 days of history to compute a level. New merchants have no baseline and are excluded from training. At run time, a new merchant with thin history may be flagged as an outlier or default to a population-level estimate (to be defined with ops).

### Minimum shop count

The trigger fires only if the area index includes at least 20 shops (rule K1, `rules.yaml`). Small zones or zones with low uptake cannot trigger, leaving merchants without a claim path (by design, to ensure statistical significance).

### Supported population

The backtest assumes every pilot shop is insured and holds cover through the entire replay. In a real pilot, uptake and churn will reduce the effective "at-risk" population, weakening the area index and triggering fewer claims.

## 9. Monitoring, drift and retraining (roadmap)

### Monitoring

- **Backtest replay:** `make demo-check` validates that the current model and policy engine produce the expected demo numbers. This is a smoke test, not live performance.
- **Logs:** Every trigger decision is logged in the audit trail (`backend/chhatri/audit/`) with facts used and the decision id.
- **Manual review:** Claims officers review REFERRED cases; dispute rates are tracked.

### Drift detection

For a real pilot, monitor:
- **Sales distribution shifts:** Compare held-out P50 predictions vs realized sales, binned by zone and shop type.
- **Claim rates:** Track the share of alerts that trigger and the payouts per zone per season.
- **Loss ratios:** Compare actual loss (actual payouts / actual premiums) vs the backtest assumption.

### Retraining schedule

- **Every season** (after monsoon): Refit the model on the latest sales data and recalibrate bounds and premiums (12-week cycle).
- **On-demand:** If drift is detected (e.g., >20% shift in zone-level loss ratios), trigger an emergency refit and compliance review.

### Data retention and lineage

- Model artifacts and training metadata are versioned in `backend/artifacts/` and tracked by `MANIFEST.json`.
- Training data (sales, rainfall, alerts) is archived in a timestamped directory; the `git_commit` field in the manifest links to the code that generated it.
- Every pilot decision is logged; the policy engine's formula and facts are recorded and auditable.

## 10. What real data would change

For a live pilot on real merchants:

1. **Training data:** Sales logs from Paytm's settlement records (live data), rainfall from Open-Metoe or a local weather API.
2. **Feature engineering:** Merchant tenure, category (food, hardware, etc.), location detail (if available), past claim history.
3. **Exclusions:** Different rules for alert days (a real alert may still have sales; only true supply-side shocks are excluded).
4. **Targets:** Real loss events (e.g., closure due to weather, theft, or civic action), labeled by merchants or inferred from extreme sales drops.
5. **Evaluation:** Real hold-out intervals, measured by actual claims filed and paid, not a simulator.
6. **Calibration:** Conformal bounds recalibrated on real zone-days; loss ratios set by actuarial analysis, not backward search.
7. **Retraining:** Automated, triggered by drift detection and seasonal cycles, not manual.

## 11. Ethical considerations

### Transparency

- Every payout is explained using the policy engine's formula and logged facts (K5: "why this amount"). The explanation is reproducible and auditable.
- The model is a tool; the policy is the decision authority (K4).
- Merchants can dispute payouts and file grievances with an SLA (K5, K9).

### Harm and fairness

- **Basis risk:** Some merchants will experience a loss without receiving a payout (forecast A8). This is disclosed in the policy (C2, C5). A real pilot must measure and disclose basis-risk rates.
- **False positives:** Payouts on non-loss days (slow days, festival closures) are tracked in the backtest (36 of 125, 29%). Merchants are not harmed by a payout they did not claim.
- **Exclusions:** Merchants with thin history or in zones with low uptake cannot access the area claim, by design (too few shops = unreliable area index). Alternative claim paths (hospital-cash, personal grievance) are available.

### Accountability

- All decisions are logged and auditable (K7, K8).
- A human reviews all REFERRED cases (slips with low confidence, doubtful names, multiple-day claims).
- Disputes are reviewed within 24 hours (K5).

## Open questions

1. What is the real basis-risk rate on live merchant data, and what disclosure is required in the policy? Owner: Omkar Kadam.
2. How should the model handle new merchants with <7 days of history? Owner: Ujjwal Pardeshi.
3. What retraining cadence and drift thresholds are feasible for a live pilot, and who owns the retrain decision? Owner: Ujjwal Pardeshi.
4. Should zone-specific lower bounds be refined using real loss labels, or held static? Owner: Ujjwal Pardeshi and the pilot partner's actuaries.

## Changelog

- 2026-10-02 · v1.4 · final consistency pass against the code: corrected training window to 18 Feb–18 Aug 2025 (includes calibration period in fit window per the training code).
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned: verified model card contains honest framing of simulated training data and circular calibration; no changes needed (compliant with canonical framing).
- 2026-10-02 · v1 · first draft, from the team's audit of the prototype (commit 86575ea).
