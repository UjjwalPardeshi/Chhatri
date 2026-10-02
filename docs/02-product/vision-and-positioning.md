# Vision and positioning

| | |
|---|---|
| Status | Draft v1 · 2 Oct 2026 |
| Owner | Omkar Kadam |
| Audience | Judges, teammates, partners, investors |
| Related | [Executive summary](../00-executive-summary.md) · [Facts and sources](../01-strategy/facts-and-sources.md) · [Roadmap in the build plan](../06-delivery/build-plan.md) |

## TL;DR

- Chhatri is income cover for small merchants where the claim starts itself, decided the same day with no forms.
- The trigger is the merchant's own sales during an alert; Paytm sees the loss and pays it with an explanation.
- Chhatri spans insurance (claim), lending (EDI holiday) and fintech (settlement), and we found no other public Track-2 project that combines all three verticals in one journey.
- Positioning: *Chhatri is income cover for India's small merchants where the claim starts itself. Paytm sees the loss in the shop's own sales, pays it the same day with no forms, explains it in Hindi, and asks the lender to give that day's loan instalment a holiday.*

## 1. The vision

**An umbrella over the merchant's best days and worst days.**

Chhatri protects a merchant's daily income when they are unable to earn. A monsoon hits the city. The merchant's sales collapse. The loan repayment comes due. Today, Chhatri is not there: the merchant waits 30–60 days for a claim decision, submits multiple documents, and pays the loan on time, reducing their ability to stock the next day. The merchant's cash buffer disappears. The next week, they borrow at high rates from a neighbour or sell inventory below cost just to stay afloat.

Chhatri changes this. When Paytm detects that the merchant's sales have dropped during a weather alert, the insurer pays them the same day—no forms, no call, no delay. Chhatri asks the lender to pause that evening's loan instalment, and the lender decides. Paytm explains why in Hindi, showing every number. The merchant can now restock the next morning. The next monsoon, the merchant has a buffer and confidence in the system.

This is what an umbrella should do: keep you dry when the rain falls, give you time to recover, and stay out of your way when the sun is out. Chhatri is that umbrella for the merchant's income.

## 2. Positioning

### The one-liner

*Chhatri is income cover for India's small merchants where the claim starts itself. Paytm sees the loss in the shop's own sales, pays it the same day with no forms, explains it in Hindi, and asks the lender to give that day's loan instalment a holiday.*

छतरी छोटे भारतीय व्यापारियों के लिए आय सुरक्षा है जहां दावा स्वयं शुरू होता है। Paytm दुकान की अपनी बिक्री में नुकसान देखता है, उसी दिन बिना किसी फॉर्म के इसका भुगतान करता है, हिंदी में समझाता है, और उस दिन की ऋण किस्त को छुट्टी देता है।

(Chhatri is income security for small Indian merchants where the claim starts itself. Paytm sees the loss in the shop's own sales, pays it the same day without forms, explains it in Hindi, and asks the lender to give that day's loan instalment a holiday.)

## 3. Why Paytm, why now

**Why Paytm:** Among fintech players we could find in public repos, Paytm has the combination needed (A1, A4, A5).

1. **Live sales per shop:** Paytm has 1.57 crore payment device merchants (A1), each with live settlement data recorded in real time. No other platform sees the merchant's sales in the moment. A competitor with only lending data or payment gateways lacks this trigger.

2. **The settlement rail:** When the insurer decides to pay, Paytm settles the money the same evening, hours after the decision. A lender on the Paytm rails can defer that evening's loan deduction immediately. No separate payout channel, no clearance delays.

3. **The Soundbox:** A Paytm Soundbox speaker is already in thousands of shops, announcing transactions in Hindi. A Soundbox message announcing the insurance payout is immediate, in the merchant's language, and has zero incremental cost.

4. **Licensed insurance distribution:** Paytm Insurance Broking holds an IRDAI direct broker licence, renewed to Feb 2029 (A4). Paytm does not underwrite; a partner general insurer will. This separation satisfies regulation while keeping Paytm as the claims operator.

5. **Merchant lending:** Partner NBFCs and banks lend on Paytm, and repayments are deducted from daily settlements (A5). An EDI holiday is credible because Paytm controls the settlement flow and the lender's rules.

**Why now:** Paytm's merchant protection plans have already proven the low-price model (under ₹2 a day, three taps to buy, 2 lakh+ merchants, A3). The barrier today is not price or trust in the brand—it is the claim process. Claims take 30–60 days and ask for multiple documents (A3). The environment is ripe: rainfall is more extreme (A13), merchants' cash reserves are thinner, and financial hardship during loss events is acute. The technology stack is available (Gemini free tier, Sarvam free credits). The regulatory path is clear: partner insurer, IRDAI sandbox route, RBI FREE-AI framework (A23), DPDP design (A22). This hackathon is the moment to build and validate it.

## 4. Target customer and the problem

**Who:** Anil Jadhav and merchants like him. A tea-stall owner in Mumbai. Hindi speaker. Earns ₹600 a day on a merchant EDI. A monsoon comes; sales vanish. The loan repayment is due. Anil is trapped between hunger and debt. He waits weeks for a claim decision and pays the loan on time by reducing what he eats or his inventory.

**The problem:** Weather-driven income loss hits hard. The merchant's best protection—the merchant's own cash sales data—is locked inside Paytm and never reaches the insurer. The insurer guesses from weather or area yields, which do not match Anil's shop. The claim takes 30–60 days. By then, Anil's debt has grown, and his business has lost momentum.

Chhatri solves this. The insurer now sees Anil's sales, decides same-day, and Chhatri asks his lender for an instalment holiday so he can recover.

## 5. Product principles

Every choice in Chhatri rests on these eight principles.

1. **The claim starts itself.** No merchant action. Paytm detects the loss and asks the insurer. If the insurer approves, Anil is paid. Chhatri calls. Chhatri checks. Chhatri pays. Anil receives.

2. **The AI builds the case; code decides the money.** The LLM extracts slip data, writes explanations, and answers questions. The policy engine, written in rules.yaml, is the only code that approves or rejects. The amount and the conditions are auditable code, not black-box predictions.

3. **Explain every rupee.** Every payout shows the formula: the expected-sales baseline, the alert that triggered it, the loss percentage, the payout share, and the cap. A merchant can read it in Hindi and understand why they got ₹1,380 and not ₹2,000. A dispute opens a case with a 24-hour answer (K5).

4. **A person for every doubt.** If the slip is unclear, the name does not match the KYC well enough, or a date is ambiguous, a claims officer reviews it (K2). Chhatri does not guess. The officer sees the merchant's own slip and the algorithm's confidence and decides.

5. **Hindi-first and voice-first.** India's merchants speak Hindi. The app defaults to Hindi, with an English toggle. Key moments—a payment announcement, a question about cover, a response to "why not paid"—come by voice and Soundbox, not text. A voice question about the amount gets a grounded answer in Hindi, citing the policy.

6. **Honest labels.** Every component on screen shows whether it is LIVE (using real API keys), SIMULATED (a labelled demo), or FALLBACK (a graceful downgrade). Nothing fools the merchant or the judge.

7. **No offers during distress.** When an alert is in force or a claim is open, Chhatri does not suggest a top-up loan, a cross-sell, or a new product (X8). The app focuses on the merchant's immediate need.

8. **Privacy by design.** Merchant sales data is synthetic for free-tier AI (A19). Hospital slips are masked and deleted on request (A22). Only purpose-specific consent is asked. The DPDP design applies now, even though substantive obligations begin May 2027 (A22).

## 6. What Chhatri is not

- **Not weather-only parametric insurance.** Chhatri uses the merchant's own sales, not a weather index or crop yield model. A heatwave hits Mumbai, but Anil's shop is in a shaded alley. Today's parametric products would pay anyway (basis risk A8). Chhatri does not.

- **Not a health insurance policy.** The hospital-cash claim reimburses lost income, not medical bills. The merchant pays their own hospital costs. Chhatri covers the income they could not earn while they were sick. This is different from health insurance.

- **Not a loan product.** The EDI holiday defers the next day's loan instalment; the lender decides whether to grant it (K3). Chhatri does not lend. RBI (Digital Lending) Directions 2025 apply to the lender (A25), not to Chhatri.

- **Not financial advice.** Chhatri does not suggest when to buy, sell, or price. It protects against income loss during a crisis, which is insurance, not advice.

## 7. Naming and brand

**"Chhatri"** means umbrella in Hindi. It is short, memorable, Hindi-first, and metaphor. An umbrella covers you. It is for everyone. You put it away when the sun is out. When the monsoon comes, you are glad you have it.

**Tone:** Professional, honest, no hype. The copy avoids generic superlatives because they hide the real story. Instead: "The claim starts itself." "The insurer decides the same day." "A person reviews unclear cases." These are strong because they are specific and true.

## 8. Roadmap horizons

Chhatri's horizons are labelled to be honest about what is built when.

| Horizon | What | When | Notes |
|---|---|---|---|
| **H0: Final day demo** | Area auto-claim (K1), hospital-cash claim (K2), EDI holiday (K3), mini-app (N1), Ask Chhatri (N2), live slip reading (N3), Hindi voice (N4), explanations and disputes (K5), console and audit (K8) | 2–3 Oct 2026 | Built before on-site; fixes and final polish on-site |
| **H1: Shadow pilot** | Consent centre (N6), grievance ladder with SLA clocks (N5), Marathi language (N8), public static demo (N7) | After hackathon | On the console only; no merchants yet |
| **H2: Live pilot** | First live merchant cohort (e.g. 10 merchants, one zone, one lender, one insurer partner); real rainfall, real sales, real claims | Q4 2026 / Q1 2027 | Hypothesis testing: dispute rate, accuracy, merchant adoption, lender confidence |
| **H3: Scale** | **Area Income Signal** (our own data product, ROADMAP): Paytm's sales index for every zone, updated hourly, public to lenders and insurers; heatwave cover for Priya in Delhi; civic disruptions (floods, strikes); Marathi in the mini-app; merchant success stories | 2027+ | Beyond this hackathon |

Our roadmap horizon H3 (scale) includes the **Area Income Signal**—a data product of Paytm's hourly sales index, built on Chhatri's data and available to lenders and insurers. This is our own roadmap idea, separate from any other Paytm initiatives.

## 9. Why Chhatri is different

The space for parametric income cover is not empty. Riskwolf sells "claimless" income cover to gig workers and SMEs (A14). SEWA offers heat-index insurance to informal workers (A9). But Chhatri's novelty is threefold:

1. **The trigger:** The merchant's own live sales inside Paytm, not a weather forecast or a district average. No area index can fake a loss; Anil's shop is one of 46 in the trigger zone. Among public players we surveyed, this real-time sales-based trigger is not found elsewhere.

2. **Settlement-linked payout:** Paytm pays the same evening, not days later. SEWA members wait weeks (A9). Because Paytm settles merchants daily, the insurer can credit the next settlement batch and the merchant sees the money by evening. No separate payout rail, no clearing delays.

3. **The EDI holiday:** Unique to merchant lending on Paytm. When the insurer pays, Chhatri asks the lender to pause the next instalment, and the lender decides. A lender on Paytm can grant it because it controls the settlement flow. The merchant keeps the full payout to restock; the lender does not lose a repayment (it is deferred, not forgiven). This is not restructuring; it is pre-agreed relief.

Together, these three moves reduce the time from loss to money from 30–60 days to hours. A monsoon hits at noon. By 17:00, Anil is paid and his next day's stock is secured.

## 10. Integration with Paytm's ecosystem

Chhatri is not an island. It is built on top of Paytm's existing infrastructure, which strengthens the case for Paytm as the operator.

- **The device:** Paytm has deployed payment devices to 1.57 crore merchants (A1). Each device records live sales. Chhatri's area index is calculated from aggregated sales in the zone, which Paytm already measures for settlement and lending decisions.

- **The settlement rail:** Paytm's payout rail is used for daily instalment debits from merchant accounts. The same rail handles insurance payouts. No new infrastructure.

- **Soundbox:** Paytm's speaker hardware in the shop broadcasts messages in Hindi. A Soundbox announcement of the payout is immediate and in the merchant's language. No SMS cost, no app-push fatigue.

- **Lending:** Partner NBFCs and banks distribute loans through Paytm, repaid via EDI. The lender would decide whether to grant an EDI holiday under a rule agreed in a pilot; no lender has agreed yet, and the lender is simulated in the prototype. Chhatri requests it via API; the lender's system grants or denies it per policy.

- **Insurance distribution:** Paytm Insurance Broking (IRDAI licensed, A4) distributes the product. Paytm does not underwrite; it facilitates. The partner insurer sets policy terms. Paytm operates the claims engine, consistent with the SPEC.

This ecosystem fit is why the idea works. Chhatri is not a new payout system or a new broker—it is a claims acceleration engine on rails that already exist.

## Open questions

1. Will a partner insurer accept the area-index trigger and the "claimless" framing? Regulatory approval path? Owner: Omkar Kadam.
2. Can the lender partner confirm the EDI-holiday policy and whether it counts as a restructuring? Owner: Omkar Kadam.
3. What will merchants pay for income cover? The backtest gives ₹6.93–₹38.82 a day by zone, while Paytm's existing plan sells for under ₹2 a day (A3). Owner: Omkar Kadam.

## Changelog

- 2026-10-02 · v1.2 · EDI holiday worded as the lender's decision; uniqueness claim hedged
- 2026-10-02 · v1.1 · final consistency pass against the code
- 2026-10-02 · v1 · first draft.
