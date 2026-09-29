# Chhatri Architecture (SPEC §0.2, §5–18)

## Core Principle

**Signals → Reasoning + Memory → Control → Action**

The AI builds the case; **code decides the money**. Only the policy engine (`chhatri.policy.engine`) can produce an `APPROVED` decision. LLM output never sets an amount, never approves, never overrides a check. Every money number shown to a merchant is reproducible from the numbers shown next to it.

## The Money Path

### 1. Expected Sales Model (SPEC §7)

One **LightGBM quantile model per quantile** (α ∈ {0.10, 0.50, 0.90}) trained on shop-hour rows:

- **Features**: `zone_id`, `shop_type`, `hour`, `dow`, `is_festival`, `month`, `shop_level`, `shop_hour_share`
- **Target**: `amount_paise / shop_level_paise` (normalised)
- **Training**: Normal days only (no alerts, no bandhs, no personal closures; ground-truth labels not available in production)
- **Determinism**: `seed=20251019`, `num_threads=1`, `force_col_wise=True`, sort predictions to fix quantile crossing
- **Calibration**: Conformal quantile on held-out 4 weeks (last week of training window); lower bound is 2.5-th percentile

Models trained with `train_end = 2025-08-18` (the day before the monsoon replay) and committed to `backend/artifacts/model/` so the demo machine never trains at startup.

API: `ExpectedSalesModel.expected_day(merchant_id, day) -> int paise` (P50 summed over business hours, rounded half-up to ₹10).

### 2. Area Trigger (SPEC §8.1–8.2)

**Every hour boundary**, compute area index for each zone:

```
index = Σ actual_paise / Σ expected_p50_paise
        over covered, open merchants in zone
        over 3-hour window [t-3h, t)
```

**Trigger fires when ALL hold**:
- An alert (rain or civic) is valid over the whole [t-3h, t) window
- Each of the 3 completed hours has `hourly_index < 50%` **and** `3h_window_index < lower_bound_pct`
- `shops_in_index ≥ 20`
- Zone hasn't already triggered that day

### 3. Area Claim (SPEC §9.1–9.3)

When a trigger fires at (zone, date) with `index_pct`, `shops_in_index`:

1. **Checks** (HARD = pass/fail; SOFT = pass/unsure/fail):

   | Check | Applies | Severity | Passes when |
   |-------|---------|----------|-------------|
   | `COVER_IN_FORCE` | all | HARD | cover exists, started, status ACTIVE |
   | `PREMIUM_PREPAID` | all | HARD | `prepaid_through ≥ event_date` (s.64VB) |
   | `COVER_BEFORE_ALERT` | area | HARD | purchased before alert issued |
   | `ALERT_ACTIVE` | area | HARD | alert valid over trigger window |
   | `INDEX_QUORUM` | area | HARD | ≥ 20 shops in index |
   | `BELOW_FLOOR` | area | HARD | all 3 hours < 50% |
   | `BELOW_MODEL_RANGE` | area | HARD | window index < zone lower bound |

2. **Decision**:
   - Any HARD fail → `DECLINED` (amount 0)
   - Else → `APPROVED`
   - Amount = `round_half_up_to_rupee(share × expected_day × drop_pct / 100)`, capped at `area_daily_cap` (₹2,500)

### 4. Personal Claim (SPEC §8.3, §9.1–9.3)

When a shop goes **silent** (zero transactions, expected P10 > 0, not weekly off, no area event):

1. **Outreach**: Next day at 11:20, if still silent by 11:00
2. **Conversation**: WhatsApp voice check-in → merchant may upload hospital slip
3. **Checks** (HARD = pass/fail; SOFT = pass/unsure/fail):

   | Check | Severity | Passes when |
   |-------|----------|-------------|
   | `SILENCE_VERIFIED` | HARD | every claimed day is a verified silent day |
   | `SLIP_READABLE` | SOFT | present, document_type medical, confidence ≥ 0.80 |
   | `NAME_MATCHES_KYC` | SOFT | score (rapidfuzz token_set_ratio) ≥ 85 |
   | `DATES_MATCH` | SOFT | admission ≤ each silent day ≤ (discharge or ∞) |
   | `WITHIN_AUTO_LIMIT` | SOFT | silent days ≤ 3 |
   | `COVER_IN_FORCE` | HARD | cover exists, started, status ACTIVE |
   | `PREMIUM_PREPAID` | HARD | prepaid through event date |
   | `NOT_ALREADY_PAID` | HARD | no approved payout for (merchant, date) |
   | `WITHIN_ANNUAL_LIMIT` | HARD | paid last 365 days + amount ≤ ₹30,000 |

4. **Decision**:
   - Any HARD fail → `DECLINED` (amount 0)
   - Any SOFT fail or UNSURE → `REFERRED` (amount is computed, case opened for human review)
   - Else → `APPROVED`
   - Amount = `days × min(round_half_up_to_rupee(share × expected_day), personal_daily_cap)` where share=0.5, cap=₹1,500

### 5. Ledger (SPEC §10)

- **Payout**: `execute(decision) → Payout` (APPROVED only; idempotent on decision_id; credited after 4 sim-min)
- **Instalment Pause**: `pause_next(merchant, event_date) → InstalmentPause | None` (pause tomorrow's instalment if exists; 5 sim-min after payout)
- **Premium Settlement**: Evening at 21:00 sim-time, if `gross_settlement_paise ≥ premium`, advance `prepaid_through` by one day

### 6. Audit Log (SPEC §11)

Append-only SQLite table:

```
hash = sha256(canonical_json({seq, at, actor, action, subject_type, subject_id, data, prev_hash}))
```

Every decision stores all checks in `data`. Chain verified via `AuditLog.verify()`.

## The Storm Replay

The **monsoon** scenario (SPEC §17.2, §17.4) replays **Tuesday 2025-08-19** with:

- **Alert**: RED rain `A-20250818-01` issued Mon 17:30, valid Tue 14:00–20:00 for Z3, Z7, Z12
- **Rain band**: 14:00–17:00 over those zones (scripted; rain impact on sales is deterministic from seed)
- **Targets** (from calibration):
  - Z7: 37% index (63% drop) → 46 shops, ₹1,380 each = ₹58,900 total
  - Z3: 38% index (62% drop) → 141 shops, varies by shop
  - Z12: 47% index (53% drop) → 125 shops, varies by shop
  - Z9: 61% slow-day (no alert, no payout)

At **17:00**:
1. Trigger fires for Z3, Z7, Z12
2. 312 shops approved for payout (total ₹ TBD by actual model)
3. **17:04**: Payouts credited; WhatsApp + Soundbox announcements
4. **17:05**: Next day's instalments paused for merchants with loans

**Determinism**: Same seed → identical numbers, ids, messages, audit hashes. Reproduced in `tests/test_golden_numbers.py`.

## The Illness Scenario

The **illness** scenario (SPEC §17.2) replays **Thursday 2025-08-21** with:

- **Anil's shop**: Silent all Wed (no sales, zero txns)
- **Outreach**: Thu 11:20, Chhatri checks in on WhatsApp
- **Reply**: Voice message "I'm in hospital with a fever" (STT + intent → `REPORT_ILLNESS`)
- **Slip**: Photo of admission slip (Sarvam vision reads: "Anil R. Jadhav", admitted 2025-08-20, "KEM Hospital")
- **Policy checks**: All HARD pass, all SOFT pass → `APPROVED` ₹1,500
- **Ledger**: Payout created, next instalment paused

Same-day payout and instalment pause (no n8n delay in local run).

## Why the LLM Can Never Approve Money

The policy engine (`evaluate_area_claim`, `evaluate_personal_claim`) is a **pure function**: facts in, decision out. It:

- Takes frozen dataclass facts (merchant, cover, trigger, slip extraction)
- Runs deterministic checks (date comparisons, name matching via rapidfuzz, cover status)
- Returns a Decision object: outcome, amount, checks, explanation

The LLM:

- **Conversation**: Detects intent, builds narrative, extracts data from slip
- **Guard**: Rejects free-text replies that contain unexplained numbers or false promises
- **Memory**: Records facts for precedents and learning

But **never** sets an amount, never approves a claim, never overrides a check. The explanation is rendered from decision facts, not free-generated. See `chhatri/conversation/guard.py` and `chhatri/policy/explain.py`.

## Deployment Architectures

### Local Development
```
Frontend (Vite :5173) ←→ Backend (FastAPI :8000, in-memory store)
                              ↓ (optional) Sarvam, WhatsApp, Paytm APIs
                              ↓ (optional) n8n
```

### Docker Compose (demo + production)
```
nginx (:80) → Backend (:8000, in-memory store)
              ↓ (optional) n8n (:5678)
              ↓ (optional) Paytm MCP (:8080)
```

## Performance Notes

- **Model training**: ≤ 30s on 8 CPU cores (26 weeks × 1000+ merchants)
- **Area index computation**: ≤ 1ms per zone per hour (vectorised with numpy)
- **Policy engine**: ≤ 5ms per claim (pure logic, no I/O)
- **Replay**: 6 sim-minutes per real second (configurable); monsoon replay (08:00–20:00) = ≤ 5 min wall-clock
- **Memory**: ≤ 2 GB for all merchants + sales + alerts + decisions + audit

See `backend/tests/` for performance assertions.
