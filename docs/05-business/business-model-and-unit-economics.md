# Business model and unit economics

| | |
|---|---|
| Status | Draft v1.5 · 2 Oct 2026 |
| Owner | Omkar Kadam |
| Audience | Judges, mentors, partners, investors |
| Related | [Facts and sources](../01-strategy/facts-and-sources.md) · [Go-to-market plan](./go-to-market-and-pilot-plan.md) · [Metrics and impact](../02-product/metrics-and-impact.md) · [Regulatory and compliance](./regulatory-and-compliance.md) |

## TL;DR

- A partner general insurer underwrites and carries the risk. Paytm Insurance Broking distributes. Paytm provides sales data, settlement rail, Soundbox and the app.
- **Hospital cash is not priced yet.** The zone premiums below cover area (monsoon) claims only. Pricing hospital-cash claims is an open question.
- Premium per zone per day = max(₹2, backtest area loss per shop ÷ 365 ÷ (1 − 0.35)); the first 30 days are prepaid, counted from the cover start date, then the evening settlement prepays each next day.
- Today's premiums come from simulated sales and give 65% loss ratio by construction; the pilot must validate on real merchants.
- On simulated sales, zone premiums run from ₹6.93 to ₹38.82 a day (Z7: ₹18.62). A Z7 merchant covered all year pays ₹6,796 against about ₹4,418 of expected area payouts. The real price is an open decision for the pilot.
- Fraud controls: area index (one shop cannot fake a loss), waiting period with alert look-ahead, KYC name match, human review, annual ₹30,000 cap.
- Why Paytm wins: 1.57 crore device merchants with live sales (A1), settlement rail, Soundbox, licensed distribution (A4), lending partnerships (A5).

## 1. Value chain

### 1.1 Who does what

| Actor | Role |
|---|---|
| Partner general insurer | Underwrites the risk, approves claims above the human-review threshold, handles reinsurance and capital. To be approached after the hackathon. |
| Paytm Insurance Broking | IRDAI-licensed broker (A4). Distributes the cover. Holds merchant relationships. |
| Paytm (Payments and Fintech) | Provides live merchant sales data (with standing consent under DPDP); operates the settlement rail and evening premium collection; operates Soundbox for payout announcements; hosts the mini-app and console; no underwriting. |
| Paytm merchant lender (NBFC / bank partner) | Grants EDI holidays per their pre-agreed rules. Chhatri requests; the lender decides, including whether the deferred instalment carries any charge (we propose none). |
| Chhatri policy engine | Deterministic, auditable checks with thresholds in `rules.yaml`. Approves, refers to a person, or declines; the only authority over payouts. |

### 1.2 Coverage and cover start

- Cover is bought through a payment link sent in the chat (the 30-day prepayment; BUILT, link SIMULATED). Buying inside the Paytm for Business app is the mini-app (N1, BUILT behind a flag).
- **Premium paid upfront:** first 30 days (link), then daily settlement deduction (standing consent).
- **Cover starts:** 7 days after purchase (the waiting period), and each day's cover needs that day's premium received first (s.64VB cash before cover).
- **Waiting period:** 7 days, always. A quote while an alert is active or forecast within 72 hours is marked BLOCKED: the new cover cannot apply to that alert, though the merchant can still buy cover for later (K6).

## 2. Revenue lines

### 2.1 Insurer's premium revenue

Zone-specific daily premium, collected for each merchant in cover. Example: Z7 merchant pays ₹18.62 per day from premiums.json; Z1 merchant pays ₹13.55.

Priced as: backtest area loss per shop per monsoon season ÷ 365 days ÷ (1 − 0.35), with a ₹2 floor. The 0.35 loading is our assumption, to be confirmed with the partner insurer.

### 2.2 Broker remuneration (Paytm Insurance Broking)

Paytm Insurance Broking earns a broker commission from the insurer, subject to IRDAI guidelines. We state no specific rate, to be negotiated with the insurer partner and approved by IRDAI.

### 2.3 Retention and lending-book benefits to Paytm (hypothetical)

Two benefits, to be validated in the pilot:

1. **Merchant stickiness:** The policy could reduce missed loan payments during loss events. The 5–10% fall in missed-payment callbacks that we sometimes quote is an illustrative hypothesis, not a measurement.
2. **Settlement friction:** Higher daily transaction volumes near claim-detection events may boost settlement flow if merchants restock sooner.

Neither is revenue; both are operational hypotheses. The pilot measures them: renewal rate in month 2 (target ≥ 80%), missed payments on shock days with and without a granted holiday, and the lender's grant rate (target ≥ 90%). Paytm's income from this product is distribution commission and merchant retention.

## 3. Pricing method

### 3.1 Formula

**Premium per day = max(₹2, expected annual loss ÷ 365 ÷ (1 − 0.35))**

- **Expected annual loss:** the backtest's area payouts in a zone, per shop per monsoon season (each monsoon is one policy year). Hospital-cash payouts are not included yet.
- **Loading (0.35):** covers the insurer's expenses, the broker's commission, reinsurance and margin. Our assumption; to be confirmed with the partner insurer.
- **Minimum (₹2 a day):** a floor so that no zone is priced near zero.

### 3.2 Current zone premiums

From `backend/artifacts/premiums.json` (derived from the simulated backtest Jun–Sep 2024 and 2025):

| Zone | Premium / day | Premium / month (30 d) | Premium / year (365 d) |
|---|---|---|---|
| Z3 (Ramesh's zone in the demo) | ₹14.16 | ₹424.80 | ₹5,168.40 |
| Z7 (Anil's zone in the demo) | ₹18.62 | ₹558.60 | ₹6,796.30 |
| Z12 (an alert zone in the demo) | ₹10.48 | ₹314.40 | ₹3,825.20 |
| Z21 (lowest of the 24 zones) | ₹6.93 | ₹207.90 | ₹2,529.45 |
| Z6 | ₹29.84 | ₹895.20 | ₹10,891.60 |
| Z8 (highest of the 24 zones) | ₹38.82 | ₹1,164.60 | ₹14,169.30 |

### 3.3 First payment: 30-day prepayment

When a merchant buys cover, they pay 30 days of premium upfront through a Paytm payment link. The link is SIMULATED today, because the team has no Paytm keys.

Example: a Z7 merchant buys on 1 Aug and pays ₹558.60. Cover starts on 8 Aug, after the 7-day waiting period, and the payment prepays the 30 days from the start date (8 Aug to 6 Sep). The 7 days between the purchase and the start are not paid for and not covered. When the 30 days run out, the evening settlement prepays each next day's ₹18.62.

### 3.4 Daily renewal: settlement deduction

On the last prepaid day, at 21:00 IST (simulated in the prototype), the evening settlement step:
1. Takes the merchant's gross collections for that day.
2. If they cover the next day's premium, prepays it.
3. Records a SETTLEMENT_DEDUCTION payment.

If the day's collections are below the premium (₹18.62 in Z7), nothing is deducted and the cover lapses after the prepaid date.

**Assumption to test:** merchants keep cover because a same-day payout on a shock day is worth more to them than its average cost.

### 3.5 Pricing simulator (BUILT, flag `h24_whatif`)

The console's Backtest page ends with **Price the cover**: the same formula as §3.1, applied to every area trigger of the backtest at five index floors (40, 45, 50, 55 and 60%), with the payout share, the area daily cap and the loading as levers (`GET /api/pricing`, table `backend/artifacts/pricing/events.json`). For each zone it shows the premium per day, month and year, the expected payout per shop, today's premium and the loss ratio that premium would run at, and, city-wide, the share of real drops paid and of payouts on a day with no real drop. At the published levers it reproduces `premiums.json` and the backtest report exactly (a test holds this). It is a planning tool for the pilot conversation, with the limits of §3.6: area claims only, simulated sales, one monsoon counted as a policy year.

### 3.6 Honest calibration note

Today's premiums are derived from simulated merchant sales (with real rainfall data from Jun–Sep 2024 and 2025). The simulation parameters are searched so the demo replay reproduces the stated numbers (e.g., Z7 at 37% sales index, Anil's ₹1,380 payout). As a result, every zone's **backtest loss ratio is about 65% by construction**.

This is **specification validation**, not performance evidence. A 65% loss ratio leaves 35% of premium for expenses, the broker's commission, reinsurance and margin. But it is not proof that real merchants will generate these numbers. The pilot must validate on real data.

## 4. Unit economics: one merchant per year

### 4.1 Illustrative merchant-year (Z7, backtest pricing)

| Item | Value | Basis |
|---|---|---|
| Premium per day | ₹18.62 | `premiums.json` |
| Premium for a full year | ₹6,796 | ₹18.62 × 365 |
| Expected area payouts per year | about ₹4,418 | 65% of premium, by construction |
| The same in Anil-sized payouts | about 3 payout days | ₹4,418 ÷ ₹1,380 |
| Left for expenses, commission, reinsurance and margin | about ₹2,379 | 35% of premium |

Hospital-cash payouts come on top: the backtest price covers area claims only, so a real price must add them (see Open questions).

### 4.2 Sensitivity: what if real merchants trigger more or less often?

| Real area payouts vs the backtest | Payouts a year | Loss ratio | Left for expenses and margin | Reading |
|---|---|---|---|---|
| 0.5× | ₹2,209 | 33% | ₹4,588 | Over-priced; the price can come down |
| 1.0× (as priced) | ₹4,418 | 65% | ₹2,379 | As designed |
| 1.4× | ₹6,185 | 91% | ₹612 | Crosses the pilot's 90% kill line |
| 2.0× | ₹8,835 | 130% | −₹2,039 | Loss-making; re-price or tighten the trigger |

**Key insight:** viability turns on how often real merchants trigger, which only the pilot can measure. The kill criteria in the [go-to-market plan](go-to-market-and-pilot-plan.md) stop the product if the loss ratio runs above 90% or below 30%.

### 4.3 Paytm's perspective: commission and cost to serve

Paytm Insurance Broking earns a commission from the insurer, paid out of the loading. We state no rate: it is negotiated with the insurer within IRDAI's rules.

Assumed incremental costs to serve one merchant for a year (all assumptions, to be measured in the pilot):

| Cost | Amount | Notes |
|---|---|---|
| Free-tier AI (demo only) | ₹0 | Synthetic data only; not usable with real merchants |
| Production AI | ₹200–₹500 | Paid tier for slip reading and chat (assumption) |
| Settlement processing | ₹50–₹100 | Marginal; the settlement rail already exists (assumption) |
| Soundbox payout announcement | ₹20–₹50 | One speaker message per payout (assumption) |
| **Total** | **₹270–₹650** | |

Whether distribution pays for itself depends on the commission rate and the cost to serve; both are pilot questions. The larger potential benefits to Paytm are the hypotheses in section 2.3.

## 5. Fraud and abuse controls

The policy rules (`rules.yaml`, version pilot-0.1) include:

### 5.1 Area-index floor (K1)

An area claim pays only if the zone-wide sales index stays **below 50% for 3 consecutive hours and below the zone's lower bound, during a RAIN or CIVIC alert, with ≥20 shops in the index**.

**Economic role:** One merchant's collusion (pretending no sales, getting paid) is invisible if 20+ other shops have real sales that push the index above 50%. The index is computed from the pool, not per shop.

### 5.2 Waiting period + alert look-ahead (K6)

- **Waiting period:** 7 days after purchase.
- **Alert look-ahead:** if an alert for the zone is active or forecast within 72 hours, the quote is marked BLOCKED: the new cover cannot apply to that alert. A hard check (COVER_BEFORE_ALERT) means cover bought after an alert was issued never pays for it.

**Economic role:** stops merchants buying cover only when a loss is already forecast.

### 5.3 KYC name match (K2)

For hospital-cash claims, the slip's patient name must match the KYC name with a token-set fuzzy-match ratio ≥ 85 (rapidfuzz). Family members cannot claim on the merchant's policy. A mismatch is a SOFT failure: the claim goes to a claims officer, not to an automatic decline.

**Economic role:** Prevents a merchant from submitting slips from relatives, inflating claim frequency.

### 5.4 Slip confidence floor (K2)

- The slip reader's confidence must be at least 0.80 (Gemini is the first provider in the chain and ran live on 3 Oct 2026, then Sarvam Vision; with no key, the labelled simulator).
- Below 80%, the slip is REFERRED to a human, not auto-approved.

**Economic role:** Blurry or forged slips are reviewed before payout.

### 5.5 Human review threshold (K2)

- Area claims: approved automatically when every hard check passes. They are never referred, though a merchant can dispute.
- Hospital-cash claims: approved automatically only for up to 3 days with every check passing (name, slip, dates). A failed or unsure slip check, or more than 3 days, sends the whole claim to a claims officer (REFERRED). A failed hard check, such as cover not in force, declines it.
- Paying twice for the same day is blocked by a hard check (NOT_ALREADY_PAID).

**Economic role:** Doubtful cases get a second pair of eyes before the insurer pays.

### 5.6 Annual cap (K4)

- Per merchant: ₹30,000 a year.
- Covers area and hospital-cash payouts together, over a rolling 365 days (a hard check).

**Economic role:** Puts a ceiling on per-merchant annual loss exposure.

### 5.7 Daily payout cap (K1, K2)

- Area claim: ₹2,500 per shop per day.
- Hospital-cash claim: ₹1,500 per day, for up to 3 days automatically.

**Economic role:** Prevents a merchant from claiming unrealistic losses on one day, even if the index is low.

These controls live in `backend/chhatri/policy/rules.yaml` and the policy checks. No language model can change them. A claims officer can waive only soft checks on a referred personal claim (recorded as WAIVED_BY_OFFICER); hard checks and thresholds change only with a new rules version.

## 6. Capital and reinsurance

The partner insurer is responsible for:
- **Capital adequacy:** IRDAI-required solvency margins.
- **Reinsurance:** To manage tail risk (e.g., a city-wide flood that triggers 1,000 claims at once).
- **Claims reserve:** Per-zone and aggregate reserves for IRDAI filing.

Chhatri's role is claims adjudication and payout orchestration; the insurer bears the underwriting risk.

**Assumption:** a partner insurer accepts a target loss ratio around 65% for this cover. The pilot will show whether real merchants stay in that band.

## 7. Why this is good for Paytm

### 7.1 Core business fit

1. **Device merchant stickiness (A1, A3):** Paytm serves 1.57 crore device merchants (A1). Existing merchant protection plans show demand at under ₹2 a day (A3). Chhatri could reduce merchant churn during monsoons (hypothesis to validate in the pilot).

2. **Settlement fintech revenue (A2):** Paytm's financial services revenue grew 45% YoY to ₹814 crore (A2). Insurance distribution is a natural add-on to lending and payment volume. Each merchant claim could lift transaction count if merchants restock sooner after payouts (hypothesis to be measured in the pilot).

3. **Licensed distribution (A4):** Paytm Insurance Broking is IRDAI-licensed and renewed to Feb 2029. Chhatri will use the existing broker licence; the partner insurer would file the product with IRDAI (section B of facts and sources).

4. **Lending-book improvement (A5):** Paytm partners with NBFCs and banks on merchant lending. EDI holidays could reduce missed payments on shock days, reducing losses that trigger default-loss protections in those lending partnerships (A5; hypothesis to test in the pilot).

5. **Soundbox reuse:** Paytm's payment devices already announce payments. A payout announcement is a marginal feature. In the prototype the Soundbox line is simulated.

### 7.2 Honest limits (what we don't claim)

- We do not claim that Chhatri will "grow to a crore merchants by 2030" without a pilot proving unit economics.
- We do not claim the 35% margin will be 40% or higher; reinsurance, claims operations, and capital costs may exceed 35%.
- We do not claim EDI holidays will reduce defaults by 10%; the pilot measures this.
- We do not invent "₹50 crore annual revenue from Chhatri" without validating the model on real merchants in the pilot.

## 8. What the pilot must validate

| Hypothesis | How to measure | Target |
|---|---|---|
| Real-merchant loss ratio stays ≤ 65% | Payouts ÷ premiums in the shadow + live phases | ≤ 70% (allow 5% tolerance) |
| Merchants maintain cover (renewal rate) | Merchants in month 2 ÷ merchants in month 1 | ≥ 80% |
| Claims are resolved in 24 hours (K5) | Median case resolution time | ≤ 24 h from opening |
| Human-review cases are fair (disputes < 5%) | Disputed cases ÷ reviewed cases | < 5% |
| EDI holiday acceptance (lender willingness) | Lender approves ≥ 90% of requests | ≥ 90% |
| Grounded answers are accurate (N2, BUILT, not measured) | Eval set: citations match policy ([AI evaluation plan](../04-engineering/ai-evaluation-plan.md)); not measured yet | ≥ 95% (target) |
| Cost per payout is sustainable | (AI + operations cost per claim) | < 10% of average payout |

## Open questions

1. What reinsurance rate will the partner insurer quote for a 65% loss ratio? Owner: Omkar Kadam.
2. Will claim payouts improve renewal rates among merchants with lending partnerships (proposed threshold: > 2% reduction in missed payments on shock days)? Owner: Omkar Kadam.
3. What broker remuneration will the partner insurer offer within IRDAI limits? Owner: Omkar Kadam.
4. How should hospital-cash claims be priced alongside the area cover, which the backtest price does not include? Owner: Omkar Kadam.

## Changelog

- 2026-10-02 · v1.5 · TL;DR says plainly that hospital cash is not priced yet; the 30 prepaid days are counted from the cover start date; the Paytm link is SIMULATED (no keys); index rule names the RAIN or CIVIC alert; hospital-cash outcomes corrected (SOFT failure or more than 3 days is REFERRED, hard failure is DECLINED); the unmeasured 5–10% figure is labelled a hypothesis and a pilot measurement plan added.
- 2026-10-02 · v1.4 · unit economics rebuilt on the backtest pricing identity (65% loss ratio) with a sensitivity table; prices from the artefact; cover start and BLOCKED wording; officer waiver rule
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned
- 2026-10-02 · v1.2 · corrections after a second read against the code
- 2026-10-02 · v1.1 · fact-check pass.
- 2026-10-02 · v1 · first draft.
