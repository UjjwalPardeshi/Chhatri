# Pitch and judge Q&A

| | |
|---|---|
| Status | Draft v1.4 · 2 Oct 2026 |
| Owner | Omkar Kadam |
| Audience | Judges, mentors, press |
| Related | [Round-1 deck](../../Chhatri%20%C2%B7%20Build%20for%20India%20AI%20Hackathon%20%C2%B7%20Track%202.pdf) · [Demo runbook](demo-runbook.md) · [DEMO.md](../DEMO.md) · [Competitive landscape](../01-strategy/competitive-landscape.md) · [Facts and sources](../01-strategy/facts-and-sources.md) · [Current-state audit](../01-strategy/current-state-audit.md) |

## TL;DR

- **The pitch is a three-act story:** the problem (a rain day halves sales, the instalment is still cut, claims take weeks), the solution (the claim starts itself: sales trigger, settlement payout, loan holiday) and why Paytm.
- **3-minute cut:** hook → the trigger on the live map → Anil's money and his "why" → who decides money → close.
- **7-minute cut:** the same, plus the dispute (EXPLAINED), the hospital-cash claim, the name mismatch (HUMAN), cover after a forecast (BLOCKED), the audit chain, the honest backtest and what is real.
- **Key lines** are in section 4. Deliver them word for word.
- **Honest disclosures:** the prototype was pre-built (29 Sep–1 Oct); the 2–3 Oct work (N1–N4, X1–X8) shows in the git log; merchant sales and the alert feed are simulated; the calibration is circular by design; the clock is accelerated; any live AI runs on free tiers with synthetic data only.
- **51 judge questions with answers** follow, grouped by theme. Every answer is backed by [facts and sources](../01-strategy/facts-and-sources.md), the code or a feature spec.
- **Things never to say** are listed in section 7.

## 1. Narrative arc and positioning

**Positioning line:** *Chhatri is income cover for India's small merchants where the claim starts itself. Paytm sees the loss in the shop's own sales, pays it the same day with no forms, explains it in Hindi, and gives that day's loan instalment a holiday.*

**Act 1: Problem.** A merchant faces two shocks on a rain day: lost sales, and a loan instalment still cut from that evening's settlement. Merchant claims have typically taken 30–60 days and several documents (A3). The merchant waits, loses trust and doesn't renew.

**Act 2: Solution.** Chhatri watches the shops' own sales inside Paytm. When a weather alert and a ward-wide sales drop are both true, the policy engine approves at once and the money goes out with that evening's settlement, with no claim form. Chhatri explains the amount in Hindi and asks the lender to pause the next instalment.

**Act 3: Why Paytm.** Paytm already has the pieces in one place: live payments from 1.57 crore device merchants (A1), the daily settlement rail that loan instalments already ride (A5), the Soundbox on the counter, a licensed insurance broker (A4), merchant lending through partner NBFCs and banks (A5), and a merchant protection plan that already covers 2 lakh+ merchants (A3). Insurance (the claim), lending (the holiday) and payments (the settlement) meet here.

## 2. Three-minute pitch

The clicks and screen states are in the [demo runbook](demo-runbook.md#2-the-3-minute-cut). Slide numbers refer to the round-1 deck, as in [DEMO.md](../DEMO.md).

| Time | Slide | What Omkar says | Notes |
|---|---|---|---|
| 0:00–0:30 | 3 | **Hook:** "Anil runs a tea stall in Parel. On a day of heavy rain his sales fall by more than half, and his ₹600 loan instalment is still cut from his settlement. Today, getting paid for that day takes 30 to 60 days of forms and documents. Paytm already sees his sales fall, as it happens. With Chhatri, the claim starts itself, and he is paid the same evening." | DEMO.md wording. Anil is a synthetic persona; never call him a real merchant. |
| 0:30–1:15 | 6 | **The trigger:** "This is Mumbai, ward by ward, in our monsoon replay: real rainfall, simulated shop sales. A red rain alert covers three wards from 14:00." … "The drop held for three hours across all 46 shops in Zone 7, below 50% and below the bottom of the model's range, during the alert. No one filed anything." … "312 shops, paid four minutes after the trigger, with the evening settlement." … "Zone 9 also dipped, with no alert. A slow day is not a loss event." | KPI tiles: 3 zones, 312 shops, 4 min. Say "37%", not the deck's 41%. |
| 1:15–2:15 | 7 | **The money:** "Anil's phone: ₹1,380, credited with today's settlement, and the Soundbox says it out loud. He asks: 'Why did I get only this much?'" … "His usual Tuesday is ₹4,380, his area fell 63%, and Chhatri pays half the lost sales. Half of ₹4,380 times 63% is ₹1,380. Every number can be checked. The AI builds the case; code decides the money." | The Soundbox line is simulated and labelled. Use the N1 mini-app only if it passed rehearsal. |
| 2:15–2:45 | 8 | **Trust:** "Who decides the money? An area drop: Chhatri pays, and a person looks only if the merchant disputes. A personal claim: the AI reads the hospital slip, and if anything is unclear, a person decides. Cover bought once a storm is forecast never covers that storm. The AI never has authority over money. Code decides." | Matches slide 8 and the `/policy` page. |
| 2:45–3:00 | 13 | **Close:** "Paytm already has the live sales, the settlement rail and the lending partners. Our next step is a pilot with a partner insurer and lender. The claim starts itself." | No partner has agreed yet: say "next step", never "we are working with". |

## 3. Seven-minute pitch

The order follows DEMO.md, so each scenario is loaded once. The clicks are in the [demo runbook](demo-runbook.md#3-the-7-minute-cut).

| Time | Beat | What Omkar says (key words) | Notes |
|---|---|---|---|
| 0:00–0:30 | Hook (slide 3) | As in the 3-minute cut. | |
| 0:30–1:30 | Trigger (slide 6) | As in the 3-minute cut, plus the Z7 panel row by row and "Why Zone 9 got nothing: its sales fell to 61% on a day with no weather alert. That's a slow day, not a loss event." | |
| 1:30–2:15 | Money and "why" (slide 7) | As in the 3-minute cut, plus "Tomorrow's ₹600 instalment is paused." | The pause comes at 17:05. |
| 2:15–2:40 | Test 1: EXPLAINED | "Anil says his loss was bigger. Chhatri doesn't argue and doesn't change the amount. It sends the case to a claims officer, who answers within 24 hours." | Chip: Sent to a claims officer · case C-2291. |
| 2:40–3:40 | Hospital-cash claim | "Anil's shop had no sales all of Wednesday while his area was normal. Nobody filed a claim: Chhatri checks in first." … "One photo of the hospital slip. The slip reader takes the name and dates; the policy engine checks them against KYC and the silent day. Half his usual Wednesday is ₹2,150, capped at ₹1,500 a day. ₹1,500, credited with today's settlement." | If the vision badge reads SIMULATED, say "the slip reader", never "the AI model read it live". |
| 3:40–4:25 | Test 2: HUMAN | "The slip says Sunil Pawar. The name doesn't match Anil's KYC, so no money moves. A claims officer sees the slip, the names and the checks, and approves. The engine re-runs every hard check before it pays." | Decision REFERRED (NAME_MATCHES_KYC), then ₹1,500 after approval. |
| 4:25–4:55 | Test 3: BLOCKED | "Monday evening. A red alert for tomorrow has just been issued. Ramesh asks for cover. New cover starts after the 7-day waiting period, from 25 August, so it won't apply to tomorrow's alert. He can still buy cover for later. Nobody can buy cover once a storm is forecast." | Link: ₹424.80 for 30 days (₹14.16 a day, from the backtest; pricing is open). |
| 4:55–5:40 | Trust (slides 5 and 8) | "Every step, from trigger to decision, payout, pause and message, is hash-chained. The chain check: valid. And here is who may decide money." | `/audit` → Verify chain; `/policy`. |
| 5:40–6:10 | Honest limits (slide 11) | "We ran the rules over the 2024 and 2025 monsoons with real rainfall and simulated sales. Chhatri caught 89 of 148 real drops, against 49 for a weather-only trigger, with far fewer payouts that had no real drop. The calibration is circular by design, and the price gives a 65% loss ratio by construction. This validates the rules, not the market." | 36 of 125 Chhatri payouts lacked a real drop, against 287 of 336 for weather-only. |
| 6:10–6:35 | What is real | "What runs live here: the policy engine, the forecast model, the audit chain and the console. [Name only the AI components the badges show as LIVE.] Simulated and labelled: shop sales, the alert feed, WhatsApp, the Paytm link, KYC, payouts and the lender. Code decides the money, and every step is logged." | DEMO.md's close line also lists WhatsApp and Paytm staging as live; that needs keys we don't have, so use this line. |
| 6:35–7:00 | Close (slide 13) | "Chhatri is income cover where the claim starts itself: paid the same evening, explained in Hindi, with the loan instalment paused. Our next step is a pilot with a partner insurer and lender. The code is public on GitHub. Questions?" | |

## 4. Key lines (deliver word for word)

| Line | When | Why it matters |
|---|---|---|
| "The claim starts itself." | Hook and close | The core value: detection and payout with no merchant action. |
| "The AI builds the case; code decides the money." | The "why" answer and the disclosure | The design: language models explain; a deterministic engine decides. |
| "A slow day is not a loss event." | Zone 9 on the live map | Basis risk: the trigger needs an alert and a drop the model can't explain. |
| "The AI never has authority over money. Code decides." | Trust beat and any doubtful case | Safety and auditability. |
| "Paytm already has the live sales, the settlement rail and the lending partners." | Close | Why Paytm (A1, A3, A4, A5). |

## 5. Honest disclosures

| Disclosure | How to say it | When |
|---|---|---|
| **Pre-built work** | "We built the prototype between 29 September and 1 October, before the final. The organisers confirmed pre-built work is allowed. Everything added on 2 and 3 October is in the git log with its date." | If asked, or if time allows. |
| **Simulated sales and alerts** | "The rainfall is real Open-Meteo data. The shops' sales and the alert feed are simulated, so the replay shows the rules work as specified, not that they work on real merchants." | Backtest beat, or "Is this real data?" |
| **Accelerated clock** | "The replay runs at 6 simulated minutes per real second, so an hour takes 10 seconds. 'Four minutes to money' is simulated time; in the product the credit rides the evening settlement." | If asked about timing. |
| **Circular calibration** | "We searched simulation parameters so the replay reproduces the demo numbers: Z7 at 37%, ₹4,380, ₹58,900. And we priced cover so the backtest loss ratio is 65%. That is specification validation, not market proof. The pilot tests real merchants." | Backtest beat, or "Isn't this circular?" Say it calmly. |
| **What is live** | Only the components the header badge shows as LIVE. Today that can be Sarvam's speech, chat and vision with our key; Gemini only after N2 and N3 land. WhatsApp and the Paytm link are simulated: we have no keys for them. Free tiers get synthetic data only. | Disclosure beat. |
| **Deck erratum** | "The round-1 sketch showed Z7 at 41%. The prototype shows 37%, which produces the 63% drop and the ₹1,380 payout." | If asked about the deck. |
| **Public, not open source** | "The repository is public. We haven't added a licence yet." | If asked about open source. |

## 6. Judge questions and answers

### A. Product and customer journey

**Q1: Isn't this just parametric insurance?**
> It pays by rule, like parametric cover, but the index is different. Parametric products usually use an external index such as rainfall or area crop yield (A8, A14). Chhatri's index is the merchants' own sales inside Paytm, pooled across a ward and checked against a weather alert. That cuts basis risk: in our backtest on simulated sales, a weather-only trigger paid 287 times without a real drop, Chhatri 36 times ([facts and sources](../01-strategy/facts-and-sources.md), section D). Riskwolf and SEWA show income cover by index exists (A14, A9); the sales trigger, the settlement payout and the loan link are what is new.

**Q2: Why a hospital-cash claim rather than a regular health insurance claim?**
> A health policy reimburses the bill. A hospital daily cash benefit pays a fixed amount per day in hospital, whatever the bill (A16). For a merchant, the shock is the closed shop: no sales, and the instalment still due. So Chhatri frames it as income: one silent day, half the usual day's sales, capped at ₹1,500 a day. It walks the track's health-claims example end to end ([fs-02](../02-product/feature-specs/fs-02-hospital-cash-claim.md)).

**Q3: Why a waiting period? Isn't blocking cover unfriendly?**
> Without it, merchants would buy only when a storm is forecast. So new cover always starts 7 days after purchase. A quote while an alert is active or forecast within 72 hours is marked BLOCKED with that explanation, and a hard check means cover bought after an alert was issued never pays for that alert. The merchant can still buy cover for later ([fs-07](../02-product/feature-specs/fs-07-cover-purchase-and-consent.md)).

**Q4: What if the lender says no to the EDI holiday?**
> The payout is still credited. The holiday is the lender's decision under its own board-approved policy (section B): Chhatri asks, quoting the decision, and the lender decides on the loan's state. Fix X4 adds a guard so Chhatri asks only when the loan is active, not in arrears and has a holiday left. If the lender declines, the instalment is due as normal and the merchant is told. In the prototype the lender is simulated ([fs-03](../02-product/feature-specs/fs-03-edi-holiday.md)).

**Q5: What if the merchant doesn't speak Hindi?**
> Today every message exists in Hindi and English, as fixed templates filled from the decision's numbers, not machine translation. Marathi is planned through the same catalogue (N8). A merchant can always ask for a person: a dispute goes to a claims officer with a 24-hour SLA.

**Q6: Can Paytm use sales data for this without the merchant's permission?**
> No. The design asks for purpose-specific, withdrawable consent to use sales for cover and claims, separate from the standing consent for the premium deduction. We design now for the DPDP Rules, 2025, whose substantive obligations apply from 14 May 2027 (A22). The consent centre (N6) is planned.

**Q7: What if the sales data is missing, say Paytm's feed is down?**
> No data, no area payout. The trigger needs at least 20 shops in the index and three full hours below the floor; if the data isn't there, the quorum check fails and the engine declines rather than guessing. Area claims have only hard checks, so they are never approved by hand. How to re-run a window after an outage is a design point to agree with the insurer.

**Q8: What if a merchant says "I lost more than you paid"?**
> They can dispute, and a claims officer answers within 24 hours. The amount comes from the policy formula, not from assessing each loss, so a dispute doesn't change it: the officer confirms the payout or rejects the dispute with a note, and the merchant is told. That is the trade-off of index cover: fast and automatic, but by formula. If an officer ever found an error in the inputs, the correction would go through the policy engine, never a manual payment.

### B. Insurance and regulation

**Q9: Who underwrites this cover?**
> Nobody yet. A partner general insurer will be approached after the hackathon. Paytm Insurance Broking holds an IRDAI broker licence valid to 16 Feb 2029 and would distribute the cover (A4). Paytm does not underwrite.

**Q10: Doesn't s.64VB (cash before cover) get in the way?**
> It shapes the design. An insurer may not assume risk until the premium is received. So cover for a day starts only when that day's premium has been received: either the first 30-day prepayment or the previous evening's settlement deduction, made with the merchant's standing consent. The 30 days is our product design, not a rule in s.64VB. To be confirmed with the partner insurer's compliance team (section B).

**Q11: If claims are automatic, how do you control the loss ratio?**
> The rules set the triggers and caps; the price sets the margin. In the prototype each zone's premium is the backtest's expected area loss ÷ (1 − 0.35), so the backtest loss ratio is about 65% by construction. An insurer would re-price on real data. If the loss ratio runs high, it can raise the premium, lower the payout share or the cap, or tighten the floor.

**Q12: Your backtest is circular, isn't it?**
> Yes, by design, and we say so. We searched simulation parameters so the replay reproduces the demo numbers (Z7 37%, ₹4,380, ₹58,900). That shows the rules behave as specified on this replay, not that they work on real merchants. The pilot tests real merchants.

**Q13: What will the loss ratio be in the real market?**
> We don't know yet. The 65% is built into the price, on simulated sales. Real merchants, lenders and insurers will differ. That is why the pilot comes before any launch, with kill criteria on the loss ratio ([go-to-market plan](../05-business/go-to-market-and-pilot-plan.md)).

**Q14: What about fraud?**
> One shop can't move a ward's index: the trigger needs at least 20 shops in the index, and one shop's slow day pays nothing. Sales come from Paytm's own payment records, not the merchant's word. For personal claims: the silent day is checked against sales, the slip name must match KYC (score ≥ 85), the slip must be readable (≥ 0.80 confidence), and anything doubtful goes to a person. A 7-day waiting period, an annual limit of ₹30,000 and a no-double-payment check close the rest.

**Q15: What if no insurer or lender wants to partner?**
> Then there is no product yet, and we will have learned something real about timing or value. A pilot needs both partners.

### C. Lending and the EDI holiday

**Q16: Why would a lender grant an EDI holiday?**
> Our hypothesis: pausing one instalment on a shock day costs less than a missed instalment and the collections effort after it, and a merchant helped through a bad day stays a customer. The pilot must test that with a lender. Whether a pre-agreed holiday counts as a restructuring is the lender's call (section B, A25). The alternative is for the insurer to pay the instalment as part of the payout ([fs-03](../02-product/feature-specs/fs-03-edi-holiday.md)).

**Q17: Is an EDI holiday a restructuring?**
> Not necessarily. As designed, it moves one instalment to the end of the loan. Whether that counts as a restructuring is for the lender's compliance team to decide; we don't claim either way.

**Q18: What if the loan has monthly instalments?**
> Paytm's merchant loans are repaid by daily deductions from settlements (A5), so we designed for daily instalments. For a monthly instalment, the same request could cover part of it; that is a lender product decision.

**Q19: Could the insurer pay the instalment instead, so the loan terms never change?**
> Yes. [fs-03](../02-product/feature-specs/fs-03-edi-holiday.md) describes this as the alternative lender setting. Which model a lender prefers is a pilot question.

### D. AI and ML

**Q20: What AI is actually live here?**
> Only what the header badge says. The policy engine and the forecast model are deterministic code, not generative AI, and they are the only authority over money. Today's AI adapters are Sarvam's: speech-to-text, text-to-speech, chat and vision. Each is live only when our Sarvam key is set; otherwise a labelled simulator runs. Intent detection is a word list; the chat model only sees text the word list can't classify. On 2–3 Oct we are adding Ask Chhatri and live slip reading, with the Gemini free tier first and Sarvam second.

**Q21: Why not let the LLM decide the amount?**
> Because it can invent a figure or a promise. The checks are deterministic Python with thresholds in a versioned YAML file (`rules.yaml`, pilot-0.1). Language models explain and converse; every amount a merchant sees comes from the decision.

**Q22: How does the forecast model work?**
> A LightGBM quantile model (p10, p50, p90) of expected sales, trained on simulated sales driven by real Open-Meteo rainfall for Colaba and Santacruz. Training window 18 Feb–18 Aug 2025; the conformal lower bound is calibrated on 22 Jul–18 Aug 2025. The area trigger needs all of: an alert valid for the whole window, three consecutive hourly indices below 50%, the window below the conformal lower bound, and at least 20 shops in the index ([ML model card](../04-engineering/ml-model-card.md)).

**Q23: How do you evaluate slip reading?**
> Honestly: not yet on real slips. Today the reader is Sarvam Vision when our key is set, otherwise a simulator that reads data embedded in synthetic sample slips. The safety net is in the rules: below 0.80 confidence, a KYC name score below 85, or dates that don't match the silent day, and a person decides. Before a pilot we would build a labelled set of synthetic and consented slips and measure field accuracy.

**Q24: Why Sarvam and Gemini rather than your own model?**
> Cost and language. Sarvam works well in Hindi and its starter credits are free. The Gemini API free tier is the planned first provider for Ask Chhatri and slip reading. Free tiers may use content to improve their products, so we send only synthetic demo data (A19). Providers sit behind adapters (`backend/chhatri/integrations/registry.py`), so an insurer could swap in a contracted or self-hosted model.

**Q25: How slow is slip reading?**
> Our client allows Sarvam's document AI up to 60 seconds; other live calls time out at 10 seconds. The merchant isn't standing at a counter: they send a photo and get a decision message. If the reader fails or times out, the claim goes ahead with an unreadable slip, which sends it to a claims officer instead of failing. An offline Tesseract fallback is planned.

**Q26: How do you handle model drift?**
> The model is fixed at build time: `make data` is the only thing that retrains it, and its outputs are committed with a manifest of hashes. The rules are versioned (pilot-0.1). In a pilot we would track payouts without a real drop, real drops missed, the share of personal claims sent to a person and the dispute rate, and retrain or re-price on that evidence.

### E. Data and privacy

**Q27: What personal data do you handle?**
> In the product: sales from Paytm's payment records, the KYC name, consent records, and for a personal claim the slip photo and the fields read from it (patient name, dates, hospital, document type). The prototype stores the slip image so a claims officer can see it on a referred case; the audit log records which fields were read but never the patient's name. All prototype data is synthetic. For a pilot: minimise and mask health data, a retention period agreed with the insurer, deletion on request (section B).

**Q28: Can merchants delete their data?**
> That is the design of the consent centre (N6, planned): withdrawing consent stops new use of sales data for cover and claims, and slip data is deleted on request; records the insurer must keep for claims and grievances are kept for the agreed period. The prototype doesn't have the consent centre yet.

**Q29: Does free-tier AI send merchant data to Google or Sarvam?**
> Today, only to Sarvam, and only when our key is set. After the 2–3 Oct work, also to the Gemini free tier for Ask Chhatri and slip reading. Free tiers may use content to improve their products (A19), so we send only synthetic demo data. With real merchants, the insurer would choose paid, contracted or self-hosted models.

**Q30: Do you have a data processing agreement?**
> No. This is a prototype on synthetic data. Before a pilot we would agree one with the insurer and lender, covering retention, deletion and third-party access.

### F. Business model and unit economics

**Q31: Who pays, and how much?**
> The merchant pays the premium; the partner insurer carries the risk and pays claims; Paytm Insurance Broking earns a commission for distribution (A4). The first payment prepays 30 days by a Paytm link; after that, the evening settlement takes the next day's premium with standing consent. The price is open. The prototype's backtest gives ₹6.93–₹38.82 a day by zone (₹14.16 in Z3, ₹18.62 in Z7), while Paytm's existing merchant plan sells for under ₹2 a day (A3). Finding a price that works for both is a pilot question.

**Q32: What does it cost to run per merchant?**
> In the demo, close to nothing: free-tier AI on synthetic data and open-source tools (LightGBM, n8n). At pilot volume the variable costs are a slip read per personal claim and speech per conversation, at paid-tier prices we would confirm then; the fixed costs are hosting, claims officers and operations. The cost figures in the [business model](../05-business/business-model-and-unit-economics.md) are labelled assumptions.

**Q33: How do you make money if the code is public?**
> The code is public on GitHub; we haven't added a licence yet. The money is in the product: the insurer earns its underwriting margin, Paytm Insurance Broking earns commission, and the lender gains fewer missed instalments if the pilot proves it. Public code is a credibility signal: partners and regulators can read the engine that decides the money.

**Q34: What's the market size?**
> We don't quote a market-size figure we can't defend. The scale facts: 1.57 crore merchants paid for Paytm payment devices in Q1 FY27 (A1), and Paytm's merchant protection plan already covers 2 lakh+ merchants (A3). The pilot starts in shadow mode in one city, then a few hundred live merchants ([go-to-market plan](../05-business/go-to-market-and-pilot-plan.md)).

**Q35: What if the loss ratio is 80%, not 65%?**
> The insurer's margin shrinks, so it would raise the premium or reduce the payout share or caps. If neither works for merchants, the product stops. The 65% is there because we priced it that way; real data may differ, and the pilot's kill criteria cover this.

### G. Technology and scale

**Q36: How many merchants can this handle?**
> Today it is one FastAPI process with SQLite, sized for a demo. The heavy work is per ward, not per merchant: one index per ward per hour, then a payout batch. For scale: Postgres (on the roadmap), workers per city or zone, and payouts through the settlement rail. Free-tier rate limits are the first bottleneck, removed with paid tiers.

**Q37: What happens if the backend crashes?**
> In the prototype: restart the process and reload the scenario; loads are deterministic, and the audit chain check shows whether anything was altered. Production needs replicated storage and more than one instance. We haven't measured recovery times, so we don't quote any.

**Q38: Could this work with lenders outside Paytm?**
> The design is lender-agnostic: sales, KYC and loan status in; a decision and a holiday request out. We focus on Paytm because the sales data, the settlement rail, the Soundbox and the lending partners sit together there.

**Q39: What if the replay or n8n stalls on stage?**
> We present with the in-process workflow runner, which doesn't hold. With n8n live, the clock holds at 17:00 for about 30–60 seconds while 312 payout runs go through n8n; the runbook says to avoid that on stage. The demo also has one-line backup commands for every control.

**Q40: How do you test without real Paytm data?**
> Simulated scenarios (monsoon, illness, illness_mismatch, buy_cover) with synthetic sales and real rainfall. At commit 86575ea: 1,711 fast and 36 slow backend tests at 99.7% coverage, 262 of 264 frontend tests (fix X1 covers the other 2), 118 infra tests, 70 of 70 demo checks through the HTTP API, and 21 Playwright end-to-end tests.

### H. Competition and novelty

**Q41: How is Chhatri different from Praman?**
> Praman, another Mumbai Track-2 project, focuses on health-claim readiness, with a deterministic rule engine, an honest-wording test and Marathi voice. We share the rule that money decisions stay out of the LLM. Chhatri starts the claim itself from the merchant's sales, pays with the settlement and links the payout to the loan instalment. Praman's README states 703 tests; we have 1,747 backend tests plus frontend, infra and demo checks. We adopted its honest-wording test idea (X7).

**Q42: How is Chhatri different from Claim Advocate?**
> Claim Advocate reviews a submitted claim against the policy, with an evidence trace, exact and semantic retrieval, and a human check of extracted slip data. Chhatri's area claim needs no submission at all, and its decisions come from a deterministic engine with a hash-chained audit log. We adopted its idea of letting the merchant confirm extracted data before checks run (N3).

**Q43: What makes the automatic claim unique?**
> Among the projects we could find in public repos, the others help a person file, check or dispute a claim. None pays automatically from the merchant's own sales, and none links the payout to a loan instalment ([competitive landscape](../01-strategy/competitive-landscape.md)).

**Q44: What did you learn from other teams?**
> We credit each idea in the [competitive landscape](../01-strategy/competitive-landscape.md): Nirdesh's journey steps with "you are here" (our tracker), the evidence traces with source badges in Sahaj, SAHAAY and Claim Advocate (our "why this amount" card), Praman's honest-wording test (X7), FinPath AI's readiness checklist and zero-login demo (N3, N7), Claim Advocate's merchant check of extracted data (N3), and Vanifi's and One-Tap Credit's rule of no loan offers during distress (X8). These are in our plan for 2–3 Oct.

### I. Team and execution

**Q45: All 76 commits are by one person. Why?**
> Ujjwal wrote and committed the prototype's code between 29 Sep and 1 Oct. Omkar led the product, regulatory and business work, the docs and the pitch. From 2 Oct, each of us commits our own work under our own name, so the split shows in the log.

**Q46: What if one of you is unavailable on the day?**
> Either of us can run the demo alone: the script and the operator steps are in the demo runbook, and every control has a one-line backup command. If the live demo can't run at all, the static demo and backup video (N7) are planned for exactly that.

**Q47: Did you build all of this on the day?**
> No, and we say so up front. The prototype was built 29 Sep–1 Oct; the organisers confirmed pre-built work is allowed. The git log shows exactly what was added on 2 and 3 Oct, and when.

**Q48: How long did this take?**
> The git history shows the prototype's 76 commits between 29 Sep and 1 Oct 2026, and everything since. We didn't log hours, so we don't quote a figure.

### J. Challenges and next steps

**Q49: What was the hardest technical problem?**
> Making the trigger honest. A weather-only trigger pays on rain whether or not sales fell; a sales-only trigger pays on slow days. Requiring both, with the model's lower bound and a 20-shop quorum, is what cut payouts without a real drop from 287 to 36 in the backtest. The second was keeping AI away from money: every amount comes from the engine, and every message is a template filled from the decision.

**Q50: What is the hardest business problem?**
> Finding an insurer and a lender who trust the risk model while our evidence is simulated. An insurer will worry about adverse selection (only exposed merchants buy) and about merchants shifting takings to cash on alert days. The pilot's shadow phase measures the trigger on real sales before any money moves.

**Q51: What would you do with another month?**
> Finish whatever of N5 (grievance ladder), N6 (consent centre) and N8 (Marathi) doesn't land on 2–3 Oct; validate the trigger on real 2026 monsoon sales; build a labelled slip test set; and agree the EDI-holiday terms with a lender ([go-to-market plan](../05-business/go-to-market-and-pilot-plan.md)).

## 7. Things never to say

| Claim | Why not |
|---|---|
| "The backtest proves this works on real merchants." | It runs on simulated sales with real rainfall. |
| Any specific claim, dispute or default reduction ("cuts disputes by X%") | We have no evidence for it yet. |
| "Anil is a real merchant." | He is a synthetic persona in a simulated replay. |
| "We are working with an insurer or lender", or any partner timeline | No partner has agreed. A partner will be approached after the hackathon. |
| "The 8-hour on-site build is official." | It is reported, not published by the organisers. |
| "RBI says an EDI holiday is not a restructuring." | Not verified. It is the lender's call. |
| Any amount for free-tier API credits, or a Gemini model version | Not published, and it changes. Say "free starter credits" or "Gemini free tier". |
| "Gemini is our fallback." | Gemini is planned as the first provider for Ask Chhatri and slip reading. |
| "WhatsApp is live" or "the Paytm link is live on staging" | We have no keys for either; both are simulated and labelled. |
| "An officer can raise the payout on a dispute." | A dispute never changes the amount. |
| "This feature is live" for a SIMULATED component, or a FALLBACK badge before X6 | The claim must match the screen. |
| "Open source" | The repository is public, with no licence yet. |
| Any hours spent, uptime or recovery-time figure | Not measured. |
| Any rival team member's name | Name projects and teams only. |

## 8. Resources to point judges to

- **Code:** github.com/UjjwalPardeshi/Chhatri (public; licence not yet added).
- **Demo:** live on the final day. The static demo URL and the backup video (N7) are added here once deployed.
- **Docs:** the [documentation index](../README.md).
- **Tests:** `make test-backend` and `make test-slow` (1,711 + 36), `make test-frontend` (264 tests, 262 passing until X1), `make test-infra` (118), `make demo-check` (70 of 70).
- **Audit:** the `/audit` page and `GET /api/audit/verify`.

## Open questions

1. If a judge asks about fairness of pre-built work, how much detail do we give? Owner: Omkar Kadam. Proposed answer: the commit dates and the organisers' confirmation, plainly.
2. If a judge presses on the circular calibration, what is our strongest next step to show? Owner: Omkar Kadam. Proposed answer: the shadow phase on real 2026 monsoon sales in the pilot plan.
3. Should we add an open-source licence before the final so we can say "open source"? Owner: Ujjwal Pardeshi.
4. DEMO.md's close line lists WhatsApp and Paytm staging as live. Update it (with its tests) or keep using the corrected line in section 3? Owner: Ujjwal Pardeshi.

## Changelog

- 2026-10-02 · v1.4 · final pitch fact-check: 7-minute order follows DEMO.md; disputes never change the amount; BLOCKED, trigger, Gemini and live/simulated wording corrected; "public", not "open source"; invented figures removed (market size, hours, uptime, slot time); test counts complete
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned
- 2026-10-02 · v1.2 · logic and truth audit fixes
- 2026-10-02 · v1.1 · fact-check pass: converted private note references to public citations (facts-and-sources.md, feature specs, ADRs, DEMO.md, SPEC.md).
- 2026-10-02 · v1 · first draft. Covers narrative arc, 3-min and 7-min pitch outlines, key lines, honest disclosures, judge questions with answers, things never to say.
