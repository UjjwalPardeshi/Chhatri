# Pitch and judge Q&A

| | |
|---|---|
| Status | Draft v1.6 · 3 Oct 2026 |
| Owner | Omkar Kadam |
| Audience | Judges, mentors, press |
| Related | [Final deck and video script](final-deck-and-video-script.md) · [Round-1 deck](../../Chhatri%20%C2%B7%20Build%20for%20India%20AI%20Hackathon%20%C2%B7%20Track%202.pdf) · [Demo runbook](demo-runbook.md) · [DEMO.md](../DEMO.md) · [Build plan](build-plan.md) · [Competitive landscape](../01-strategy/competitive-landscape.md) · [Facts and sources](../01-strategy/facts-and-sources.md) · [Current-state audit](../01-strategy/current-state-audit.md) · [AI evaluation plan](../04-engineering/ai-evaluation-plan.md) |

## TL;DR

- **The pitch is a three-act story:** the problem (a rain day halves sales, the instalment is still cut, earlier claims took weeks), the solution (the claim starts itself: sales trigger, settlement payout, a request to the lender for an instalment holiday) and why Paytm.
- **3-minute cut:** hook → the trigger on the live map → Anil's money and his "why" → who decides money → close. It uses slides 1, 3, 4, 8 and 12 of the [final deck](final-deck-and-video-script.md).
- **7-minute cut:** slides 1 to 12 of the same deck. It adds the four stages of the claims journey (understand the cover, submit one slip photo, track the claim, resolve a query), the dispute (EXPLAINED), the name mismatch (HUMAN), cover after a forecast (BLOCKED), the source behind every number, the audit chain, AI with honest labels, the business model with the honest price, the honest limits and the ask.
- **Key lines** are in section 4. Deliver them word for word.
- **Honest disclosures:** the prototype was pre-built (29 Sep–1 Oct); everything since is built in waves behind flags and shows in the git log, and a feature that is not finished and rehearsed at the freeze is hidden, never shown half-working; merchant sales and the alert feed are simulated; the calibration is circular by design; the clock is accelerated; live AI runs on free tiers with synthetic data only; no insurer or lender has agreed to anything.
- **78 judge questions with answers** follow, grouped by theme (A to K). Section K holds the hardest ones: the price against Paytm's under-₹2 plan, payouts without a real drop, slip accuracy, how much AI there is, partners, adverse selection and what is built. Every answer is backed by [facts and sources](../01-strategy/facts-and-sources.md), the code or a feature spec.
- **Things never to say** are listed in section 7.

## 1. Narrative arc and positioning

**Positioning line:** *Chhatri is income cover for India's small merchants where the claim starts itself. Paytm sees the loss in the shop's own sales, pays it the same day with no forms, explains it in Hindi, and asks the lender to give that day's loan instalment a holiday.*

**Act 1: Problem.** A merchant faces two shocks on a rain day: lost sales, and a loan instalment still cut from that evening's settlement. Earlier Paytm merchant plans took 30–60 days per claim and several documents (A3). The merchant needs the money that week and is left waiting.

**Act 2: Solution.** Chhatri watches the shops' own sales inside Paytm. When a weather alert and a ward-wide sales drop are both true, the policy engine approves at once and the money goes out with that evening's settlement, with no claim form. Chhatri explains the amount in Hindi and asks the lender to pause the next instalment.

**Act 3: Why Paytm.** Paytm already has the pieces in one place: live payments from 1.57 crore device merchants (A1), the daily settlement rail that loan instalments already ride (A5), the Soundbox on the counter, a licensed insurance broker (A4), merchant lending through partner NBFCs and banks (A5), and a merchant protection plan that already covers 2 lakh+ merchants (A3). Insurance (the claim), lending (the holiday) and payments (the settlement) meet here.

## 2. Three-minute pitch

The clicks and screen states are in the [demo runbook](demo-runbook.md#2-the-3-minute-cut). Slide numbers refer to the [final deck](final-deck-and-video-script.md), whose run of show sets the times below. The runbook's tables should match them (open question 4).

| Time | Slide | What Omkar says | Notes |
|---|---|---|---|
| 0:00–0:30 | 1 | **Hook:** "Anil runs a tea stall in Parel. On a day of heavy rain his sales fall by more than half, and his ₹600 loan instalment is still cut from his settlement. Getting paid for a day like that has typically taken 30 to 60 days of forms and documents. Paytm already sees his sales fall, as it happens. With Chhatri, the claim starts itself, and he is paid the same evening." | DEMO.md wording. Anil is a synthetic persona; never call him a real merchant. The 30 to 60 days is what the case study reports for earlier plans (A3): never say "today". |
| 0:30–1:15 | 3 | **The trigger:** "This is Mumbai, ward by ward, in our monsoon replay: real rainfall, simulated shop sales. A red rain alert covers three wards from 14:00." … "The drop held for three hours across all 46 shops in Zone 7, below 50% and below the bottom of the model's range, during the alert. No one filed anything." … "312 shops, paid four minutes after the trigger, with the evening settlement." … "Zone 9 also dipped, but it had no alert. A slow day is not a loss event." | Seek to 14:30 before Play, so the replay takes about 33 seconds (from 13:30 it takes 43). KPI tiles: 3 zones, 312 shops, 4 min (simulated time). Say "37%", not the round-1 deck's 41%. |
| 1:15–2:10 | 4 | **The money:** "Anil's phone: ₹1,380, credited with today's settlement, and the Soundbox says it out loud. He asks: 'Why did I get only this much?'" … "His usual Tuesday is ₹4,380, his area fell 63%, and Chhatri pays half the lost sales. Every number can be checked." … "Chhatri also asks his lender to pause tomorrow's ₹600 instalment. In this replay the lender is simulated and says yes. A real lender decides." … "Half of ₹4,380 times 63% is ₹1,380. The AI builds the case; code decides the money." | The Soundbox line is simulated and labelled. Use the mini-app only if it passed rehearsal (N1, wave 1). The built chat line reads "Tomorrow's ₹600 instalment is paused." until X4 (wave 1) changes it: do not read it out as Chhatri's act. |
| 2:10–2:40 | 8 | **Trust:** "Who decides the money? An area drop: Chhatri pays, and a person looks only if the merchant disputes. An unclear slip: a person decides. Cover bought once a storm is forecast never covers that storm. The AI never has authority over money. Code decides." | Slide only in this cut. Matches the `/policy` page. |
| 2:40–3:00 | 12 | **Close:** "Paytm already has the live sales, the settlement rail and the lending partners. What you saw runs on simulated sales and real rainfall, and no insurer or lender has agreed yet. Our next step is a pilot with both. The claim starts itself." | No partner has agreed yet: say "next step", never "we are working with". |

## 3. Seven-minute pitch

The order follows the [final deck](final-deck-and-video-script.md), slides 1 to 12, and loads each scenario once, in the order of DEMO.md. The clicks are in the [demo runbook](demo-runbook.md#3-the-7-minute-cut). A slide that depends on a flagged feature has a version without it: use it unless the feature passed rehearsal (final deck, section 4).

| Time | Slide and beat | What Omkar says (key words) | Notes |
|---|---|---|---|
| 0:00–0:30 | 1 · Hook | As in the 3-minute cut. | |
| 0:30–0:50 | 2 · Four stages | "The track asks for four stages of a claims journey: understand the cover, submit documents, track the claim, resolve queries. We will walk all four, starting with a claim nobody files." | Slide only. Show the built column of the stage table for any stage whose feature is hidden. |
| 0:50–1:45 | 3 · Trigger | As in the 3-minute cut, plus the Z7 panel row by row and "Why Zone 9 got nothing: its sales fell to 61% on a day with no weather alert. That's a slow day, not a loss event, so Chhatri doesn't pay." | Seek to 14:00 before Play (about 38 seconds of replay). |
| 1:45–2:30 | 4 · Money, "why" and dispute | As in the 3-minute cut except its last sentence, plus **Test 1, EXPLAINED:** "Anil says his loss was bigger. Chhatri doesn't argue and doesn't change the amount. It sends the case to a claims officer, who answers within 24 hours." | Chip: Sent to a claims officer · case C-2291. The instalment step comes at 17:05 on the simulated clock. |
| 2:30–3:20 | 5 · Understand the cover, then one photo | "Thursday. Anil's shop had no sales all of Wednesday while his area was normal. Nobody filed a claim: Chhatri checks in first." … "He's in hospital. One photo of the slip." … "The slip reader takes the name and dates; the policy engine checks them against KYC and the silent day. Half his usual Wednesday is ₹2,150, capped at ₹1,500 a day. ₹1,500, credited with today's settlement." | If the vision badge reads SIMULATED, say "the slip reader", never "the AI model read it live". Add the coverage explainer and pre-check lines from the deck's slide 5 only if those features shipped. |
| 3:20–4:05 | 6 · Track it, resolve it (**Test 2, HUMAN**) | "Same story, but the slip says Sunil Pawar. The name doesn't match Anil's KYC, so no money moves. A claims officer sees the slip, the extracted name, the KYC name and the checks, and approves. The engine re-runs every hard check before it pays." | Decision REFERRED (NAME_MATCHES_KYC), then ₹1,500 after approval. |
| 4:05–4:35 | 7 · Every number shows where it came from | If shipped: "Every number on this card says where it came from: the rules version, the sales index, the alert, KYC. Every explanation says what would have changed the outcome, and the engine writes that line, not a language model. Zone 9 got nothing because there was no alert. With an alert and three hours below half, it would have paid." Built today: "Every number on this panel says what it is: the alert, the sales, the cover, the payment. And Zone 9 says why it got nothing." | The receipt is wave 1 (H13, H14). Say "source", not "verified". The counterfactual wording is proposed, not in the message catalogue. |
| 4:35–5:15 | 8 · Code decides the money (**Test 3, BLOCKED**, then the audit chain) | "Who decides the money? An area drop: Chhatri pays, and a person looks only if the merchant disputes. An unclear slip: a person decides." … "Monday evening, a red alert for tomorrow has just been issued. Ramesh asks for cover. New cover starts after the 7-day waiting period, from 25 August, so it won't apply to tomorrow's alert. He can still buy cover for later." … "Every step is hash-chained, and the chain check reads valid. The AI builds the case; code decides the money." | Link: ₹424.80 for 30 days (₹14.16 a day, from the backtest; pricing is open). `/audit` → Verify chain; the payout-authority table is on the slide and on `/policy`. |
| 5:15–5:40 | 9 · AI that says what it is | "What runs live here: the policy engine, the forecast model, the audit chain and the claims console. [Say that Sarvam speech and slip reading are live only if their badges read LIVE.] Simulated and labelled: shop sales, the alert feed, WhatsApp, the Paytm payment link, KYC, payouts, the lender and the Soundbox. Language models talk to people. They never decide money, and every AI reply shows its mode." | This is DEMO.md's close line. Point at the header badges and name only what they show as LIVE. |
| 5:40–6:10 | 10 · The business model and the honest price | "A partner insurer would underwrite, and Paytm's insurance broker would distribute. We priced each zone from our own simulated losses: about seven to thirty-nine rupees a day. Paytm's existing merchant plan costs under two. We don't know whether merchants will pay several times more for income cover that pays the same evening. That is what the pilot is designed to find out. Hospital cash isn't priced yet." | If asked, go to Q52 to Q55. Never say "a few rupees a day". |
| 6:10–6:40 | 11 · What this is not, yet | "We ran the rules over the 2024 and 2025 monsoons: real rainfall, simulated sales. Chhatri paid 89 of 148 real drops against 49 for a weather-only trigger, and 36 of its 125 payouts had no real drop against 287 of 336. The calibration is circular by design: this validates the rules, not the market. No insurer or lender has agreed yet, and slip reading is not measured on real slips." | The price gives a 65% loss ratio by construction: say so if asked. The split of the 148 real drops is in Q56. Never cut this slide. |
| 6:40–7:00 | 12 · The ask | "Chhatri is income cover where the claim starts itself. Paytm already has the live sales, the settlement rail and the lending partners. Our next step is a pilot with a partner insurer and lender, on real sales, with no payouts at first. The code is public on GitHub. Questions?" | Keep slides 13 and 14 up for questions. Say "next step", never "we are working with". |

## 4. Key lines (deliver word for word)

| Line | When | Why it matters |
|---|---|---|
| "The claim starts itself." | Hook and close | The core value: detection and payout with no merchant action. |
| "The AI builds the case; code decides the money." | The "why" answer and the disclosure | The design: language models explain; a deterministic engine decides. |
| "A slow day is not a loss event." | Zone 9 on the live map | Basis risk: the trigger needs an alert and a drop the model can't explain. |
| "The AI never has authority over money. Code decides." | Trust beat and any doubtful case | Safety and auditability. |
| "Paytm already has the live sales, the settlement rail and the lending partners." | Close | Why Paytm (A1, A3, A4, A5). |
| "This validates our rules, not the market." | The honest-limits beat and any backtest question | Stops the replay being heard as market proof. |
| "No insurer or lender has agreed yet." | The honest-limits beat, the close and any partner question | We have no talks to report, so we claim none. |

## 5. Honest disclosures

| Disclosure | How to say it | When |
|---|---|---|
| **Pre-built work** | "We built the prototype between 29 September and 1 October, before the final. The organisers confirmed pre-built work is allowed. Everything added from 2 October is in the git log with its date and author." | If asked, or if time allows. |
| **Flagged features** | "Everything on our list is built behind flags, all off by default. What you see is what was switched on and rehearsed at the freeze. Anything else stays hidden, not shown half-working. The AI paths are tested against fakes, and on 3 October the stage script was also walked with a live Gemini key (slip read and a free question both labelled LIVE gemini). Sarvam has not been run: we have no key." | If asked about the mini-app, Ask Chhatri, voice or the consent centre. |
| **No partner** | "No insurer or lender has agreed to anything, and we have no talks to report. A partner insurer and lender will be approached after the hackathon." | Any partner question, and the close. |
| **Simulated sales and alerts** | "The rainfall is real Open-Meteo data. The shops' sales and the alert feed are simulated, so the replay shows the rules work as specified, not that they work on real merchants." | Backtest beat, or "Is this real data?" |
| **Accelerated clock** | "The replay runs at 6 simulated minutes per real second, so an hour takes 10 seconds. 'Four minutes to money' is simulated time; in the product the credit rides the evening settlement." | If asked about timing. |
| **Circular calibration** | "We searched simulation parameters so the replay reproduces the demo numbers: Z7 at 37%, ₹4,380, ₹58,900. And we priced cover so the backtest loss ratio is 65%. That is specification validation, not market proof. The pilot tests real merchants." | Backtest beat, or "Isn't this circular?" Say it calmly. |
| **Not measured** | "We haven't measured slip-reading accuracy, intent accuracy or merchants' willingness to pay. The evaluation page shows a number only once a stored run exists." | AI and price questions. |
| **What is live** | Only the components the header badge shows as LIVE. Today that can be Sarvam's speech, chat and vision with our key; Gemini when a Gemini key is set (`make demo-stage` is live by default; the stage script was walked live on 3 October with `gemini-2.5-flash-lite`), and a FALLBACK badge when a provider is down or unset. WhatsApp and the Paytm link are simulated: we have no keys for them. Free tiers get synthetic data only. | Disclosure beat. |
| **Round-1 deck errata** | "The round-1 sketch showed Z7 at 41%. The prototype shows 37%, which produces the 63% drop and the ₹1,380 payout. It also called WhatsApp and the Paytm link live and the price 'a few rupees a day': both are simulated, and the price is open." | If asked about the deck. |
| **Public, not open source** | "The repository is public. We haven't added a licence yet." | If asked about open source. |

### Deck vs screen

The round-1 PDF is the submitted artefact and is not edited. Where the screen differs, the screen is right. Say it plainly when asked, and never defend the PDF line.

| PDF says | The screen shows | Say |
|---|---|---|
| Slide 6: "Z7 · 41%" | `Z7 · 37% · 46 shops`; 37% of the usual day is a 63% drop, which gives ₹4,380 × 63% × ½ = ₹1,380 | "The sketch said 41%. 41% would not give our own 63% drop. The prototype's 37% does, and every number on screen traces to a source." |
| Slide 13: "What is live: Sarvam voice, the policy engine, WhatsApp, the claims console and the Paytm premium link" | Live: the policy engine, the claims console, the audit chain, real Open-Meteo rainfall, and Gemini for the slip reader and free questions when the footer says LIVE. SIMULATED: shop sales, KYC, payouts, the lender, WhatsApp, the Paytm link, and Sarvam unless a key is set | "The engine, the console and the audit chain are real. WhatsApp, the Paytm link and voice are simulators, and the header chip says so." |
| Slide 13: "Premium paid with a real Paytm link (staging)" | `paytm.me/sim-...` with a SIMULATED badge: no Paytm staging credentials | "We have no Paytm credentials, so the link is a labelled simulation." |
| Slide 9: "Sarvam runs the conversation" | Intents come from a word-list classifier first; for free text the chain is Gemini, then Sarvam, then rules, and the footer names which answered. The only model with a key on this machine is Gemini | "Rules first, so the three live tests never depend on a model's mood. A model answers only free text, and the footer says which one." |
| Slides 2 and 10: SEWA "42-56 days" / "6-8 weeks" | "Weeks" | "SEWA pays automatically after a heat trigger, and the money reaches members weeks later. We do not quote a day count." |
| Slide 12: "a few rupees a day" | Per-area premium from the backtest ledger, ₹6.93 to ₹38.82 a day (Z7 ₹18.62, about 0.4% of its ₹4,380 average day) | "Priced per area from its history; the price is open until a pilot. Compare it to a day's sales, not to the under-₹2 base plan." |
| Slide 6: rain band "14:00-17:00" | "Heavy rain band · since 14:00" (the band is still on at the time shown) | Nothing; it is the same fact. |
| Slide 7: instalment "paused by Chhatri" | With the lender flag on: "your lender has paused tomorrow's instalment", labelled SIMULATED | "Chhatri asks, the lender decides. The lender is simulated." |

## 6. Judge questions and answers

### A. Product and customer journey

**Q1: Isn't this just parametric insurance?**
> It pays by rule, like parametric cover, but the index is different. Parametric products usually use an external index such as rainfall or area crop yield (A8, A14). Chhatri's index is the merchants' own sales inside Paytm, pooled across a ward and checked against a weather alert. That cuts basis risk: in our backtest on simulated sales, a weather-only trigger paid 287 times without a real drop, Chhatri 36 times ([facts and sources](../01-strategy/facts-and-sources.md), section D). Riskwolf and SEWA show income cover by index exists (A14, A9); what Chhatri adds is a sales-based trigger, a settlement payout and a link to the loan.

**Q2: Why a hospital-cash claim rather than a regular health insurance claim?**
> A health policy reimburses the bill. A hospital daily cash benefit pays a fixed amount per day in hospital, whatever the bill (A16). For a merchant, the shock is the closed shop: no sales, and the instalment still due. So Chhatri frames it as income: one silent day, half the usual day's sales, capped at ₹1,500 a day. It walks the track's health-claims example end to end ([fs-02](../02-product/feature-specs/fs-02-hospital-cash-claim.md)).

**Q3: Why a waiting period? Isn't blocking cover unfriendly?**
> Without it, merchants would buy only when a storm is forecast. So new cover always starts 7 days after purchase. A quote while an alert is active or forecast within 72 hours is marked BLOCKED with that explanation, and a hard check means cover bought after an alert was issued never pays for that alert. The merchant can still buy cover for later ([fs-07](../02-product/feature-specs/fs-07-cover-purchase-and-consent.md)).

**Q4: What if the lender says no to the EDI holiday?**
> The payout is still credited. The holiday is the lender's decision under its own board-approved policy (section B): Chhatri asks, quoting the decision, and the lender decides on the loan's state. With the x4 flag on, a guard means Chhatri asks only when the loan is active, not in arrears and has a holiday left, and the message says that Chhatri asked and the lender decides. With the flag off, the older wording shows. If the lender declines, the instalment is due as normal and the merchant is told. In the prototype the lender is simulated ([fs-03](../02-product/feature-specs/fs-03-edi-holiday.md)).

**Q5: What if the merchant doesn't speak Hindi?**
> Today every message exists in Hindi and English, as fixed templates filled from the decision's numbers, not machine translation. Marathi text is built for the mini-app (a draft, not checked by a native speaker, no Marathi voice) and shows only if its flag is on. A merchant can always ask for a person: a dispute goes to a claims officer with a 24-hour SLA.

**Q6: Can Paytm use sales data for this without the merchant's permission?**
> No. The design asks for purpose-specific, withdrawable consent to use sales for cover and claims, separate from the standing consent for the premium deduction. We design now for the DPDP Rules, 2025, whose substantive obligations apply from 14 May 2027 (A22). The consent centre (N6) is built behind a flag and shows only if switched on at the freeze; all its data is synthetic.

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
> Yes, by design, and we say so. We searched simulation parameters so the replay reproduces the demo numbers (Z7 37%, ₹4,380, ₹58,900). That shows the rules behave as specified on this replay, not that they work on real merchants. The pilot tests real merchants. The split of the 148 real drops is in Q56.

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
> Only what the header badge says. The policy engine and the forecast model are deterministic code and a trained statistical model, not generative AI, and they are the only authority over money. Today's AI adapters are Sarvam's: speech-to-text, text-to-speech, chat and vision. Each is live only when our Sarvam key is set; otherwise a labelled simulator runs. Intent detection is a word list; the chat model only sees text the word list can't classify. Built behind flags and shown only if switched on: Ask Chhatri and slip reading with the Gemini free tier first, Sarvam second and fixed templates last, browser voice, and a provider panel with a FALLBACK badge. These chains are tested against fakes only; no live key has been run.

**Q21: Why not let the LLM decide the amount?**
> Because it can invent a figure or a promise. The checks are deterministic Python with thresholds in a versioned YAML file (`rules.yaml`, pilot-0.1). Language models explain and converse; every amount a merchant sees comes from the decision.

**Q22: How does the forecast model work?**
> A LightGBM quantile model (p10, p50, p90) of expected sales, trained on simulated sales driven by real Open-Meteo rainfall for Colaba and Santacruz. Training window 18 Feb–18 Aug 2025; the conformal lower bound is calibrated on 22 Jul–18 Aug 2025. The area trigger needs all of: an alert valid for the whole window, three consecutive hourly indices below 50%, the window below the conformal lower bound, and at least 20 shops in the index ([ML model card](../04-engineering/ml-model-card.md)).

**Q23: How do you evaluate slip reading?**
> Honestly: not yet on real slips. Today the reader is Sarvam Vision when our key is set, otherwise a simulator that reads data embedded in synthetic sample slips. The safety net is in the rules: below 0.80 confidence, a KYC name score below 85, or dates that don't match the silent day, and a person decides. Before a pilot we would build a labelled set of synthetic and consented slips and measure field accuracy.

**Q24: Why Sarvam and Gemini rather than your own model?**
> Cost and language. Sarvam works well in Hindi and its starter credits are free. The Gemini API free tier is the first provider in the chain (tested against fakes; no key run) for Ask Chhatri and slip reading. Free tiers may use content to improve their products, so we send only synthetic demo data (A19). Providers sit behind adapters (`backend/chhatri/integrations/registry.py`), so an insurer could swap in a contracted or self-hosted model.

**Q25: How slow is slip reading?**
> Our client allows Sarvam's document AI up to 60 seconds; other live calls time out at 10 seconds. The merchant isn't standing at a counter: they send a photo and get a decision message. If the reader fails or times out, the claim goes ahead with an unreadable slip, which sends it to a claims officer instead of failing. A Tesseract fallback is a later option, not in the wave-2 chain and not in the code.

**Q26: How do you handle model drift?**
> The model is fixed at build time: `make data` is the only thing that retrains it, and its outputs are committed with a manifest of hashes. The rules are versioned (pilot-0.1). In a pilot we would track payouts without a real drop, real drops missed, the share of personal claims sent to a person and the dispute rate, and retrain or re-price on that evidence.

### E. Data and privacy

**Q27: What personal data do you handle?**
> In the product: sales from Paytm's payment records, the KYC name, consent records, and for a personal claim the slip photo and the fields read from it (patient name, dates, hospital, document type). The prototype stores the slip image so a claims officer can see it on a referred case; the audit log records which fields were read but never the patient's name. All prototype data is synthetic. For a pilot: minimise and mask health data, a retention period agreed with the insurer, deletion on request (section B).

**Q28: Can merchants delete their data?**
> That is how the consent centre (N6, built behind a flag) works: withdrawing consent stops new use of sales data for cover and claims, and slip data is deleted on request; records the insurer must keep for claims and grievances are kept for the agreed period. It shows only if its flag is on at the freeze.

**Q29: Does free-tier AI send merchant data to Google or Sarvam?**
> Today, only to Sarvam, and only when our key is set. If a Gemini key is set, also to the Gemini free tier for Ask Chhatri and slip reading. Free tiers may use content to improve their products (A19), so we send only synthetic demo data. With real merchants, the insurer would choose paid, contracted or self-hosted models.

**Q30: Do you have a data processing agreement?**
> No. This is a prototype on synthetic data. Before a pilot we would agree one with the insurer and lender, covering retention, deletion and third-party access.

### F. Business model and unit economics

**Q31: Who pays, and how much?**
> The merchant pays the premium; the partner insurer carries the risk and pays claims; Paytm Insurance Broking earns a commission for distribution (A4). The first payment prepays 30 days by a Paytm link; after that, the evening settlement takes the next day's premium with standing consent. The price is open. The prototype's backtest gives ₹6.93–₹38.82 a day by zone (₹14.16 in Z3, ₹18.62 in Z7), while Paytm's existing merchant plan sells for under ₹2 a day (A3). Finding a price that works for both is a pilot question (Q52).

**Q32: What does it cost to run per merchant?**
> In the demo, close to nothing: free-tier AI on synthetic data and free tools (LightGBM, n8n). At pilot volume the variable costs are a slip read per personal claim and speech per conversation, at paid-tier prices we would confirm then; the fixed costs are hosting, claims officers and operations. The cost figures in the [business model](../05-business/business-model-and-unit-economics.md) are labelled assumptions.

**Q33: How do you make money if the code is public?**
> The code is public on GitHub; we haven't added a licence yet. The money is in the product: the insurer earns its underwriting margin, Paytm Insurance Broking earns commission, and the lender gains fewer missed instalments if the pilot proves it. Public code is a credibility signal: partners and regulators can read the engine that decides the money.

**Q34: What's the market size?**
> We don't quote a market-size figure we can't defend. The scale facts: 1.57 crore merchants paid for Paytm payment devices in Q1 FY27 (A1), and Paytm's merchant protection plan already covers 2 lakh+ merchants (A3). The pilot plan starts in shadow mode with no payouts, then goes live in stages, from a few hundred merchants to 500–1,000 in one city; these are plan sizes, not commitments ([go-to-market plan](../05-business/go-to-market-and-pilot-plan.md)).

**Q35: What if the loss ratio is 80%, not 65%?**
> The insurer's margin shrinks (at 1.4 times the backtest's payouts, Z7's loss ratio is about 91%), so it would raise the premium or reduce the payout share or caps. If neither works for merchants, the product stops. The 65% is there because we priced it that way; real data may differ, and the pilot's kill criteria cover this (Q54).

### G. Technology and scale

**Q36: How many merchants can this handle?**
> Today it is one FastAPI process with SQLite, sized for a demo. The heavy work is per ward, not per merchant: one index per ward per hour, then a payout batch. For scale: Postgres (on the roadmap), workers per city or zone, and payouts through the settlement rail. Free-tier rate limits are the first bottleneck, removed with paid tiers.

**Q37: What happens if the backend crashes?**
> In the prototype: restart the process and reload the scenario; loads are deterministic, so the same ids, amounts and audit chain are rebuilt (the store and the audit log live in memory). Production needs replicated storage and more than one instance. We haven't measured recovery times, so we don't quote any.

**Q38: Could this work with lenders outside Paytm?**
> The design is lender-agnostic: sales, KYC and loan status in; a decision and a holiday request out. We focus on Paytm because the sales data, the settlement rail, the Soundbox and the lending partners sit together there.

**Q39: What if the replay or n8n stalls on stage?**
> We present with the in-process workflow runner, which doesn't hold. With n8n live, the clock holds at 17:00 for about 30–60 seconds while 312 payout runs go through n8n; the runbook says to avoid that on stage. The demo also has one-line backup commands for every control.

**Q40: How do you test without real Paytm data?**
> Simulated scenarios (monsoon, illness, illness_mismatch, buy_cover) with synthetic sales and real rainfall. The current counts are in [facts and sources](../01-strategy/facts-and-sources.md), section D: 3,284 backend tests collected, the frontend suite, the infra suite, the demo checks through the HTTP API and the Playwright end-to-end tests. The earlier baseline (commit 86575ea) was 1,711 fast and 36 slow backend tests.

### H. Competition and novelty

**Q41: How is Chhatri different from Praman?**
> Praman, another Mumbai Track-2 project, focuses on health-claim readiness, with a deterministic rule engine, an honest-wording test and Marathi voice. We share the rule that money decisions stay out of the LLM. Chhatri starts the claim itself from the merchant's sales, pays with the settlement and links the payout to the loan instalment. We adopted its honest-wording test idea (X7), and credit it for source badges, clause citations, the slip pre-check and the grievance router in our plan (Q77).

**Q42: How is Chhatri different from Claim Advocate?**
> Claim Advocate reviews a submitted claim against the policy, with an evidence trace, exact and semantic retrieval, and a human check of extracted slip data. Chhatri's area claim needs no submission at all, and its decisions come from a deterministic engine with a hash-chained audit log. We adopted its idea of letting the merchant confirm extracted data before checks run (N3).

**Q43: What is different about the automatic claim?**
> Among the projects we could find in public repos, the others help a person file, check or dispute a claim. We did not find one that pays automatically from the merchant's own sales, or one that links the payout to a loan instalment. We may have missed some; the [competitive landscape](../01-strategy/competitive-landscape.md) lists what we reviewed.

**Q44: What did you learn from other teams?**
> We credit each idea, project by project, in the [competitive landscape](../01-strategy/competitive-landscape.md). The main ones: journey steps with "you are here" from Nirdesh, SAHAAY and FinSaathi (our claim tracker); source badges and evidence traces from Praman, Claim Advocate, Sahaj and SAHAAY (our receipt and "why this amount" card); a counterfactual in every explanation from One-Tap Credit; the honest-wording test from Praman; no loan offers during distress from One-Tap Credit and Vanifi (X8); the readiness checklist and the merchant confirming what was read from FinPath AI, FINPATH and Claim Advocate (N3); a zero-login demo from FinPath AI (N7). All of it is planned in waves and shown only if it ships.

### I. Team and execution

**Q45: All 76 commits are by one person. Why?**
> Ujjwal wrote and committed the prototype's code between 29 Sep and 1 Oct. Omkar led the product, regulatory and business work, the docs and the pitch; his first commit, the documentation set, is dated 2 Oct. From 2 Oct, each of us commits our own work under our own name, so the split shows in the log.

**Q46: What if one of you is unavailable on the day?**
> Either of us can run the demo alone: the script and the operator steps are in the demo runbook, and every control has a one-line backup command. If the live demo can't run at all, the static demo and backup video (N7) are for exactly that; the video is recorded by a person and is not in the repo yet.

**Q47: Did you build all of this on the day?**
> No, and we say so up front. The prototype was built 29 Sep–1 Oct; the organisers confirmed pre-built work is allowed. The git log shows exactly what was added from 2 Oct, and when (Q73).

**Q48: How long did this take?**
> The git history shows the prototype's 76 commits between 29 Sep and 1 Oct 2026, and everything since. We didn't log hours, so we don't quote a figure.

### J. Challenges and next steps

**Q49: What was the hardest technical problem?**
> Making the trigger honest. A weather-only trigger pays on rain whether or not sales fell; a sales-only trigger pays on slow days. Requiring both, with the model's lower bound and a 20-shop quorum, is what cut payouts without a real drop from 287 to 36 in the backtest. The second was keeping AI away from money: every amount comes from the engine, and every message is a template filled from the decision.

**Q50: What is the hardest business problem?**
> Finding an insurer and a lender who trust the risk model while our evidence is simulated. An insurer will worry about adverse selection (only exposed merchants buy) and about merchants shifting takings to cash on alert days (Q67). The pilot's shadow phase measures the trigger on real sales before any money moves.

**Q51: What would you do with another month?**
> Finish whatever of the later waves (N5 grievance ladder, N6 consent centre, N8 Marathi) is hidden at the freeze; validate the trigger on real 2026 monsoon sales; build a labelled slip test set; and agree the EDI-holiday terms with a lender ([go-to-market plan](../05-business/go-to-market-and-pilot-plan.md)).

### K. Hard questions: price, evidence, partners, AI and delivery

**Q52: Paytm's existing merchant plan costs under ₹2 a day. Why would a merchant pay several times more?**
> We don't know that they will; the price is the open question. The prototype's prices come from our own simulated losses: ₹6.93 to ₹38.82 a day by zone (₹14.16 in Z3, ₹18.62 in Z7), against under ₹2 for Paytm's existing plan (A3). That plan is a different product, and the case study we cite doesn't give its cover terms, so its price is not a like-for-like benchmark. Our hypothesis is that merchants value a payout the same evening with no forms. The pilot tests whether they buy at several price points, and which levers (payout share, cap, trigger floor) bring the price down. Hospital cash is not in these prices yet.

**Q53: Why should an insurer risk a 65% loss ratio on an untested trigger when the current product may already be profitable?**
> We don't know the existing plan's loss ratio, so we make no claim about it. The 65% is not a forecast: it is built into our prototype price (premium = expected area loss ÷ (1 − 0.35)), on simulated sales, so it shows the arithmetic and nothing more. Nobody is asked to take the risk on this evidence. The plan puts an insurer's money at risk only after a shadow phase with no payouts has compared the trigger with real sales and merchants' own reports, then through a staged pilot with stop rules (a loss ratio above 90% or below 30% in the monsoon phase) ([go-to-market plan](../05-business/go-to-market-and-pilot-plan.md)). An insurer would also price from its own data. Chhatri doesn't have to replace the existing plan: whether it is an addition, a later version or a separate cover is for Paytm and the insurer to decide.

**Q54: If you cut the price, doesn't the loss ratio break? And if the real loss ratio is worse, does a merchant get anything back?**
> Yes, if nothing else changes: the same payouts against a lower premium raise the loss ratio. At 1.4 times the backtest's payouts, Z7's loss ratio is about 91%, over the pilot's stop line ([business model](../05-business/business-model-and-unit-economics.md), section 4.2). The levers are the payout share (half today), the daily cap (₹2,500), the trigger floor (50%) and the 35% loading, and the insurer decides which to move. If none works for merchants, the product stops. No refund or profit share is designed: a merchant buys cover for the days it is in force. How refunds and the free-look period apply is the partner insurer's call ([fs-07](../02-product/feature-specs/fs-07-cover-purchase-and-consent.md), open question 5), and the prototype computes no refund.

**Q55: You pay half the lost sales, not all of it. Why would a merchant buy half a cover?**
> Half is a design setting (`payout_share: 0.5` in `rules.yaml`), chosen as a deductible that limits moral hazard and basis risk ([regulatory and compliance](../05-business/regulatory-and-compliance.md)). It is not a tested merchant preference, and the rules file marks its thresholds as illustrative, to be set with the insurer. Whether merchants value half a cover at the price is a pilot question: the pilot can vary the share and the cap and watch who buys, who renews and who disputes.

**Q56: The backtest is circular. How do you know the trigger works on real merchants?**
> We don't, and we say so. The calibration is circular by design: we searched simulation parameters so the replay reproduces the demo numbers (Z7 37%, ₹4,380, ₹58,900), and priced cover so the loss ratio is 65%. The replay shows the rules behave as specified, with real rainfall and simulated sales. The headline also mixes causes. Of the 148 real drops, 48 are zone-days of two scripted city-wide shutdown days (one per monsoon) that a rain trigger cannot see, and 50 are slow days with no alert, which Chhatri leaves unpaid by design. On the 50 rain drops, a weather-only trigger paid 47 and Chhatri 41. Proof has to come from real sales, which is what the pilot's shadow phase measures.

**Q57: 36 of 125 payouts had no real drop, and 59 of 148 real drops were missed. Isn't that a flaw?**
> It is a trade-off we show, not one we hide. Of Chhatri's 125 backtest payouts, 36 (29%) had no real drop; the weather-only trigger had 287 of 336 (85%). Of the 148 real drops, Chhatri paid 89 and missed 59: 50 of those are slow days with no alert, which the cover does not pay, and 9 are rain days. An index can pay a shop that did not lose that day and miss one that did. That is basis risk, and it is why the payout is a share of the shop's own expected day times the area's drop, not of its own loss. "Real drop" is the simulator's own definition: a zone-day losing at least 40% of expected sales. Whether real rates look anything like these is for the shadow phase to measure.

**Q58: How many of your tests use real-world data?**
> None use real merchants' data. There are 3,284 backend tests collected (fast and slow); sales, alerts, KYC, payouts and the lender are simulated, and the real inputs are Open-Meteo rainfall and the BMC ward map. Tests show that the code does what the specification says. They don't show that the specification is right for real merchants. That is what the shadow phase on real sales is for.

**Q59: Slip reading is untested on real slips. What if the reader fails half the time?**
> We haven't measured accuracy on real slips, so we quote none. The rules are built so that a failing reader costs time, not wrong money: an unreadable slip (confidence below 0.80), a name score below 85, or dates that don't match the silent day each send the claim to a claims officer, never to an automatic payment. If the reader failed half the time, half the personal claims would reach an officer, and the share referred is a number we would watch. The residual risk is a confident misread that still passes every check. Only a labelled test set can size it: before a pilot we would build one from synthetic and consented slips and measure field accuracy. The thresholds in `rules.yaml` are illustrative until then.

**Q60: The reader misreads an admission date on a referred case. What stops a false denial?**
> The reader cannot deny a claim. Slip checks are SOFT: a failed or unsure check gives REFERRED, not DECLINED. Only a HARD failure (no cover in force, an unpaid premium, no verified silent day, a claim already paid or the annual limit) gives DECLINED. A referred claim goes to an officer, who sees the slip image beside the extracted fields and can approve; approval re-runs every HARD check before any money moves. That is the HUMAN test in the demo: a name that doesn't match sends the claim to a person, and no money moves until the person decides.

**Q61: Where is the AI? Isn't this mostly rules?**
> Yes, on purpose where money is involved. The decision is deterministic code with thresholds in a versioned file, and expected sales come from a trained LightGBM quantile model with a conformal lower bound: statistical learning, not generative AI. Language and speech models sit at the edges. Today that is Sarvam adapters for speech, chat and slip vision, live only when our key is set and otherwise labelled simulators; intent detection is a word list, and the chat model sees only text the list can't classify. Gemini, Ask Chhatri, the slip pre-check and browser voice are built behind flags, tested against fakes only, and shown only if switched on. We don't claim a model decides anything.

**Q62: Why should merchants trust an AI-driven system when insurers have failed them?**
> They shouldn't have to trust the AI, because it doesn't decide the money. Every amount comes from a formula in a rules file in the public repository. The merchant sees the formula and the numbers ("why this amount"), can dispute, and can reach a person. Every step is hash-chained, so tampering shows. The code is public so it can be read, but it has not been independently audited, and we have not tested with merchants whether they trust it. That is a pilot measure.

**Q63: When will you sign an insurer and a lender, and how confident are you that they'll accept the risk model?**
> We can't give a date, and we have no talks to report: no insurer or lender has agreed to anything. A partner general insurer and a lender will be approached after the hackathon. We have no basis for confidence about their answer. What we bring is a working engine, an audit chain, a backtest we describe honestly, and a pilot plan that starts with no payouts. If a lender declines the holiday, the payout is still credited (Q4). A pilot needs both partners (Q15). Today Chhatri is a working prototype and a pilot design, not a product; if both partners said no, what we would keep is the engine, the audit chain and what we learned.

**Q64: Is the Paytm link live on staging? Be specific.**
> No. It is simulated and labelled. The team has no Paytm credentials, so the premium link in the demo is a simulated one (`https://paytm.me/sim-…`) and no request goes to Paytm. The code for Paytm's payment MCP server and for the direct REST API exists, but without credentials it has not run against Paytm. WhatsApp is simulated for the same reason: we have no WhatsApp Cloud API keys. The round-1 deck described both as live; that is not the case.

**Q65: If a merchant buys on day 20 and a storm hits on day 25, can they claim?**
> No. Cover always starts 7 days after purchase, so a purchase on day 20 starts cover on day 27, and a storm on day 25 falls inside the waiting period. A hard check also means cover bought after an alert was issued never pays for that alert. The 30 prepaid days run from the day cover starts, not from the day of payment; after them, each next day is prepaid from the evening settlement only if that day's collections cover the premium. That is how the design respects s.64VB: no day is covered before its premium is received. To be confirmed with the partner insurer's compliance team.

**Q66: Isn't a payout with no action from the merchant creepy? How do you stop merchants feeling cheated?**
> The merchant chooses it: they buy the cover and agree to the use of their sales for cover and claims, a purpose-specific consent they can withdraw (the consent screen is N6, built behind a flag). A payout arrives as a Hindi or English message that says what was paid and why, with the formula, and the merchant can ask "why", dispute, or reach a person within 24 hours. A dispute does not change the amount, so a merchant whose loss was bigger gets an answer, not a different sum. That is the trade-off of index cover: fast and automatic, but by formula. Whether merchants feel it is fair is something only a pilot can show.

**Q67: What stops merchants buying cover only before a storm, or moving sales to cash on alert days?**
> Late buying is blocked: new cover starts 7 days after purchase, a quote while an alert is active or issued for the next 72 hours is marked BLOCKED, and cover bought after an alert was issued never pays for that alert. Selection is harder: merchants who know they are exposed may buy early, which is why the price is set per zone and why the pilot would watch who buys. On cash: the index sees only payments that Paytm records, and it pools at least 20 shops, so one shop moving takings to cash cannot create an area drop, and its payout depends on the ward's drop and its expected day, not on its own sales that day. Many shops shifting to cash on alert days would pull the index down; we can't measure that on simulated sales, and the shadow phase compares the index with merchants' own reports.

**Q68: DPDP obligations start in May 2027. Why isn't the consent centre live for the demo?**
> It is built (N6) behind a flag and shown only if it is switched on and rehearsed at the freeze. All its data is synthetic. We design for the DPDP Rules, 2025, whose substantive obligations apply from 14 May 2027 (A22), because the cover cannot work without sales data, so consent has to be purpose-specific and withdrawable ([fs-07](../02-product/feature-specs/fs-07-cover-purchase-and-consent.md)). The pilot plan asks for merchant data only under explicit, purpose-specific consent.

**Q69: Hospital-cash claims aren't in the price. How will you estimate the cost?**
> We can't yet. The prototype's prices cover area claims only; hospital cash is an open pricing decision with the insurer. What we can say is that the exposure per merchant is capped by design: ₹1,500 a day, up to 3 automatic days a claim, and ₹30,000 over a rolling year. What we can't say is how often real merchants are hospitalised: the backtest's silent-shop claims use a closure rate that is a simulation setting, not evidence. An insurer would price from its own hospital-cash experience, and the shadow phase would count how often real merchants go silent. If the volume is high, the premium rises or the insurer declines.

**Q70: What is built today and what is not?**
> Built, all behind flags that are off by default: the area claim, the hospital-cash claim, the EDI holiday request, the policy engine (pilot-0.1), explanations and disputes, cover purchase with the waiting period, the hash-chained audit log and the claims console, with a WhatsApp-style phone simulator and Sarvam adapters; and the merchant mini-app (N1), Ask Chhatri (N2), slip reading with a pre-check (N3), browser voice (N4), the grievance ladder (N5), the consent centre (N6), Marathi text (N8) and the fixes X1 to X8. Not done: the backup video (N7 has the static pieces; the video is recorded by a person) and anything needing a partner. The AI paths are tested against fakes; no live key has been run. We show only what is switched on and rehearsed at the freeze.

**Q71: Where is the merchant app? I only see a claims-officer console.**
> The merchant side has two views: the phone simulator inside the console (a WhatsApp-style chat in Hindi and English, with the Soundbox strip and voice chips, at `/merchant/S-0142`) and the mini-app (N1: a cover card, a plain-words coverage explainer, a claim tracker and a trust receipt), which shows when its flag is on. The numbers are the same in both.

If the mini-app passed rehearsal, show it instead and say so.

**Q72: What if Ask Chhatri, slip reading or voice fail integration before the demo? Will you finish all of it?**
> Everything was built in waves behind flags, all off by default, with the freeze 90 minutes before the slot. A feature that is not switched on and rehearsed is hidden, not shown half-working, and each AI feature has a built fallback: chips for voice, fixed templates for chat, the sample slip and a claims officer for slips. The core engine and the audit chain don't depend on any of them. Both cuts of the pitch have a built-today version of every slide ([final deck](final-deck-and-video-script.md), section 4).

**Q73: How much of this is new, and how much was pre-built?**
> The prototype was pre-built: 76 commits by Ujjwal between 29 Sep and 1 Oct, covering the policy engine, forecast, backtest, audit chain, claims console and phone simulator. The organisers confirmed pre-built work is allowed, and we say so up front. What is new is the documentation set and the waves of work above; each commit carries its date and author, so `git log --since=2026-10-02` shows exactly the difference. We don't claim the prototype was built on the day.

**Q74: Your code is public but has no licence. Does that signal you haven't thought about distribution or regulatory sharing?**
> It signals that we haven't chosen a licence yet, and we say so. With no licence file, the code can be read but nobody else has a right to reuse it by default. We call it public, not open source. We made it public so judges and partners can read the engine that decides the money; adding a licence is an open question on our list. Distribution to merchants would go through a partner insurer and Paytm Insurance Broking, not through the repository.

**Q75: Your audit chain is in SQLite and a scenario reload resets it. Is the audit trail durable?**
> No, not in the prototype. The audit log is a hash chain in an in-memory database that is rebuilt on every scenario load (the replay is deterministic, so a reload gives the same chain), and a restart empties it. It is tamper-evident, not durable: `GET /api/audit/verify` shows whether an entry was altered, but it can't bring back entries that were lost. A production version would need durable, append-only storage with restricted write access and the latest chain hash recorded outside the system. That is a design intent, not built.

**Q76: How much of the "4 minutes to money" is real?**
> None of it is real time or real money. The 4 minutes are the payout-rail delay set in the rules (`payout_rail_delay_minutes: 4`), counted on the simulated clock, which runs at 6 simulated minutes per real second; the console slows to 1 minute per second near the payout so the audience can see it. Sales, alerts and payouts are simulated. What is real is the code path: the engine decides at 17:00 of simulated time and the credit follows after the set delay. In the product the credit rides the evening settlement, and the real delay would depend on Paytm's rail, which we haven't measured.

**Q77: Praman has Marathi voice and shipped code, and your new features are behind flags. How are you winning?**
> We can't tell how the judging will go. Where others are ahead today, we say so: several projects have merchant-facing screens and public demo links, and Praman, another Mumbai Track-2 project, has Marathi voice, while our mini-app and Marathi text are built behind flags, not yet rehearsed, and our Marathi has no voice. Test counts don't settle it either way: Praman's README gave 703 tests and later 930 on 2 Oct, and ours are 3,284 backend tests collected plus frontend, infra and demo checks. What Chhatri puts its effort into is a claim that starts itself from the merchant's own sales, a deterministic engine that alone decides money, a link to the loan instalment and a hash-chained audit log. We took ideas from Praman and credit them: the honest-wording test, source badges, clause citations, the slip pre-check and the grievance router ([competitive landscape](../01-strategy/competitive-landscape.md)).

**Q78: If the lender refuses the holiday, the merchant still owes the instalment. Is that acceptable?**
> It is the honest outcome, and the merchant is no worse off than without Chhatri. The instalment is the lender's money and the holiday is the lender's decision under its own policy: Chhatri asks, quoting the decision, and the lender grants or refuses. The payout is credited either way, and the merchant is told plainly that the lender declined, not that Chhatri paused anything. The alternative is for the insurer to pay the instalment out of the payout, so the loan terms never change (Q19); which model a lender prefers is a pilot question. In the prototype the lender is simulated and says yes, so the demo shows nothing about how a real lender would answer.

## 7. Things never to say

| Claim | Why not |
|---|---|
| "The backtest proves this works on real merchants." | It runs on simulated sales with real rainfall. |
| "Chhatri catches more real drops than a weather trigger", without the split | 48 of the 89 are scripted shutdown days. On the 50 rain drops, weather-only paid 47 and Chhatri 41 (Q56). |
| Any specific claim, dispute or default reduction ("cuts disputes by X%") | We have no evidence for it yet. |
| "Anil is a real merchant." | He is a synthetic persona in a simulated replay. |
| "We are working with an insurer or lender", "we have spoken to", "a letter of intent", a named partner or any partner timeline | No partner has agreed and we have no talks to report. A partner will be approached after the hackathon. |
| "Today it takes 30 to 60 days" or "Paytm's current plan takes 30 to 60 days" | The case study says Paytm's earlier plans did (A3). We have no figure for a current plan. |
| "Merchants will pay this price", or "a few rupees a day" | The price is open (Q52). |
| "The 8-hour on-site build is official." | It is reported, not published by the organisers. |
| "RBI says an EDI holiday is not a restructuring." | Not verified. It is the lender's call. |
| Any amount for free-tier API credits, or a Gemini model version | Not published, and it changes. Say "free starter credits" or "Gemini free tier". |
| "Gemini is our fallback." | Gemini is the first provider in the chain for Ask Chhatri and slip reading; Sarvam is second and fixed templates are last. No Gemini key has been run. |
| "WhatsApp is live" or "the Paytm link is live on staging" | We have no keys for either; both are simulated and labelled. |
| "An officer can raise the payout on a dispute." | A dispute never changes the amount. |
| "This feature is live" for a SIMULATED component, or a FALLBACK badge before X6 | The claim must match the screen. |
| The mini-app, Ask Chhatri, voice, the grievance ladder or the consent centre as live-tested | They are built behind flags and tested against fakes. Say only what is on the screen and its badge. |
| Any slip-reading, intent or other AI accuracy figure | Not measured. The evaluation page shows a number only after a stored run. |
| "The audit trail is durable" | The log is in memory and rebuilt on every scenario load (Q75). |
| "Open source" | The repository is public, with no licence yet. |
| "The only", "the first", "unique", "guaranteed" or "proven" about Chhatri | We can't back them. Say "among the projects we could find in public repos". |
| Any hours spent, uptime or recovery-time figure | Not measured. |
| Any rival team member's name | Name projects and teams only. |

## 8. Resources to point judges to

- **Code:** github.com/UjjwalPardeshi/Chhatri (public; licence not yet added).
- **Demo:** live on the final day. The static demo URL and the backup video (N7) are added here once the repo owner has deployed them and the link works.
- **Docs:** the [documentation index](../README.md).
- **Tests:** `make test-backend` and `make test-slow` (3,284 collected), `make test-frontend`, `make test-infra`, `make demo-check` (70 of 70).
- **Audit:** the `/audit` page and `GET /api/audit/verify`.

## Open questions

1. If a judge asks about fairness of pre-built work, how much detail do we give? Owner: Omkar Kadam. Proposed answer: the commit dates and the organisers' confirmation, plainly (Q73).
2. If a judge presses on the circular calibration, what is our strongest next step to show? Owner: Omkar Kadam. Proposed answer: the shadow phase on real 2026 monsoon sales in the pilot plan (Q56).
3. Should we add an OSI-approved licence before the final? Until we do, we say "public". Owner: Ujjwal Pardeshi.
4. Align the demo runbook with the final deck's run of show (slide numbers, the 3-minute and 7-minute boundaries, the replay seek times) and with DEMO.md's corrected hook. When this version was written, the runbook still used the round-1 slide numbers and the earlier hook ("Today, getting paid…"). Owner: Omkar Kadam.
5. Q71 and Q72 depend on which flagged features are on at the freeze. Who records that decision in the rehearsal log, and when? Owner: Omkar Kadam. Proposed answer: the presenter, at the second rehearsal.

## Changelog

- 2026-10-02 · v1.5 · 27 hard questions added (Q52–Q78: price against the under-₹2 plan, the split of the backtest's 148 real drops, slip accuracy, AI depth, partners, a lender that refuses the holiday, adverse selection, s.64VB timing, audit durability, pre-built work, licence, build status); timetables and slide numbers aligned to the final deck; hook says earlier plans took 30–60 days; lender-decides and waves wording; DEMO.md's close line now matches; never-say list extended
- 2026-10-02 · v1.4 · final pitch fact-check: 7-minute order follows DEMO.md; disputes never change the amount; BLOCKED, trigger, Gemini and live/simulated wording corrected; "public", not "open source"; invented figures removed (market size, hours, uptime, slot time); test counts complete
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned
- 2026-10-02 · v1.2 · corrections after a second read against the code
- 2026-10-02 · v1.1 · fact-check pass: citations point to public documents (facts-and-sources.md, feature specs, ADRs, DEMO.md, SPEC.md).
- 2026-10-02 · v1 · first draft. Covers narrative arc, 3-min and 7-min pitch outlines, key lines, honest disclosures, judge questions with answers, things never to say.
