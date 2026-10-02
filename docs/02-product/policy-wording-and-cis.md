# Policy wording and Customer Information Sheet

| | |
|---|---|
| Status | Draft v1.5 · 2 Oct 2026 (illustrative) |
| Owner | Omkar Kadam |
| Audience | Insurer partners, legal and compliance counsel, judges |
| Related | [Regulatory and compliance](../05-business/regulatory-and-compliance.md) · [Facts and sources](../01-strategy/facts-and-sources.md) · [Feature specs](feature-specs/fs-01-area-auto-claim.md) |

## TL;DR

- This is an **illustrative draft for the hackathon only**. It is not a filed or approved product. The partner insurer will write the real policy wording.
- Clause IDs C1–C12 are stable. Ask Chhatri (fs-05, PLANNED, N2) will cite them as chips (H17).
- Wording follows rules.yaml pilot-0.1: 50% payout share, area cap ₹2,500 a day, hospital-cash cap ₹1,500 a day (up to 3 automatic days), annual limit ₹30,000 over a rolling 365 days, 7-day waiting period, 24-hour dispute SLA. Anything that is not in the rules or the code yet is marked "proposed" or PLANNED.
- Covers area income loss (a RAIN or CIVIC alert plus a collapse in area sales) and hospital-cash income (slip-based). In the prototype the simulated payout rail credits the money four minutes after the decision.
- The EDI holiday is the lender's decision. Chhatri only requests it (C10).
- A Customer Information Sheet (as a table) and a one-screen Hindi summary complete the document.

---

## C1. Definitions

**Alert:** A warning issued for a zone. Two kinds can trigger cover: RAIN (heavy rain) and CIVIC (a bandh or shutdown). A HEATWAVE alert does not trigger cover. Alerts carry a colour (yellow, orange or red). The prototype does not use the colour, so a RAIN or CIVIC alert of any colour can trigger cover (see Open questions). Alerts are simulated (IMD-style) in the prototype.

**Area income loss:** A loss of merchant sales when each of 3 consecutive hourly area sales indices is below 50%, the index for the whole 3 hours is also below the zone's lower bound from the forecasting model, and an alert already issued covers the zone for the whole 3 hours.

**Area sales index:** Actual sales in the zone's covered shops divided by their expected sales, for one hour or for the 3-hour window, as a percentage. At least 20 shops must be in the index for a valid trigger.

**Expected day:** The forecasting model's median (P50) estimate of a merchant's sales for a given date. It uses the shop's own recent sales level (last 56 days), its zone and shop type, the day of the week, the month and festivals. Weather is not an input, so it describes a normal day. Expected days are rounded to ₹10. The payout is half the expected day × the percentage drop.

**Hospital slip:** A document from a hospital (admission slip, discharge summary, prescription or bill) showing the patient name, admission and discharge dates, hospital name and the nature of admission (e.g. "Viral fever").

**KYC name:** The legal name registered when the merchant's Paytm account was opened and verified.

**Silent day:** A completed day on which the merchant's shop had no Paytm sales at all in its business hours (the payments its Soundbox announces), although the shop normally sells something on a working day (the low end of its usual daily range is above zero). It is not the shop's weekly off day, and the zone had no area event that day.

**EDI (equated daily instalment) holiday:** A request by Chhatri for the lender to move the next day's loan instalment to the end of the loan after a payout. Whether the lender grants it is the lender's decision under its board-approved policy.

**Settlement:** The transfer of the payout amount to the merchant's Paytm wallet or bank account. In the prototype the simulated payout rail credits it 4 minutes after the decision.

**Drop:** The percentage of expected sales lost: 100% − the area sales index of the 3-hour window that triggered the claim.

---

## C2. Coverage: Area income loss

**What we cover.**
- When a RAIN or CIVIC alert is issued for a zone and you are a covered merchant in that zone, we check the area sales index every hour.
- If each of the last 3 hourly indices is below 50%, and the index for the whole 3 hours is also below the zone's lower bound from the forecasting model, the area income loss claim is triggered automatically. You do not need to do anything.
- You are paid half your expected day's sales × the drop percentage, up to a daily cap of ₹2,500 per merchant.

**Example:**
- You are a tea stall owner in Parel, Zone Z7, with an expected daily sales of ₹4,380.
- On 19 August at 17:00, an alert covers your zone. The area index is 37% (down 63%).
- Your payout = 50% × ₹4,380 × 63% = ₹1,380. In the prototype the simulated rail credits it at 17:04 (simulated time).

**When we do not cover area income loss (nothing is paid):**
- No RAIN or CIVIC alert, already issued, covers your zone for the whole 3 hours. A HEATWAVE alert does not count.
- The area index is not below 50% in each of the 3 hours, or not below the zone's lower bound.
- Fewer than 20 covered shops are in the zone's index.
- You did not have cover in force on that day, your waiting period (7 days) was still running, or your premium was not prepaid through that day.
- You bought cover after the alert was issued.
- You were already paid for that day, or the annual limit would be passed.

---

## C3. Coverage: Hospital-cash income loss

**What we cover.**
- If your shop has a silent day (no sales at all, see C1), we message you the next morning at 11:20 to ask if everything is okay. A voice version of this check-in is PLANNED (N4).
- You send one photo of a hospital document (admission slip, discharge summary, prescription or bill).
- If the slip shows your name (score of at least 85 against your KYC name), the slip dates cover the silent days, the slip is readable (at least 80% confidence) and the claim is for 3 days or fewer, we approve your claim automatically.
- You are paid half your expected day's sales, up to ₹1,500 per day, for up to 3 days automatically. For more than 3 silent days, a person reviews the claim.
- In the prototype the simulated rail credits the money 4 minutes after the decision.

**Example:**
- You were admitted to KEM Hospital on 20 August with a viral fever. Your shop had no sales all day on 20 August.
- On 21 August at 11:20, we message you. You reply (by voice note or tap), then send a photo of your admission slip.
- Your name on the slip ("Anil R. Jadhav") scores 100 against your KYC name. We approve ₹1,500 (half of ₹4,300 is ₹2,150, capped at ₹1,500 for 1 day).

**When the claim goes to a person instead of being paid automatically (REFERRED, not declined):**
- The name on the slip scores below 85 against your KYC name, or is not in Latin script.
- The slip dates do not cover the silent days.
- The slip is not readable enough (below 80% confidence) or is not a medical document.
- The claim is for more than 3 silent days.

**When the claim is declined (nothing is paid):**
- You did not have cover in force on the silent day, or your premium was not prepaid through it.
- The sales data do not show the silent day.
- You were already paid for that day, or the annual limit would be passed.

---

## C4. How much we pay

### C4.1 Payout formula

Payout = **50% × Expected day × Drop %**, subject to daily and annual caps.

- **Expected day:** The forecasting model's median sales estimate for you on that day (see C1). For a hospital-cash claim it is the expected day of the first silent day.
- **Drop %:** (100% − the area sales index of the trigger window) for area claims; 100% for hospital-cash (we assume the full day was lost).
- **Payout share:** We cover 50% of the loss; the other 50% is your deductible.

### C4.2 Daily caps

- **Area income loss:** Maximum ₹2,500 per merchant per day.
- **Hospital-cash income loss:** Maximum ₹1,500 per merchant per day, for up to 3 days automatically. Beyond 3 days, a person reviews.

### C4.3 Annual limit

The total payout across all claims (area and hospital-cash) cannot exceed ₹30,000 per merchant in any rolling 365-day period.

### C4.4 What we do not pay

- Claims for days outside your cover period.
- Claims before your cover starts (7 days after you ask for it).
- Amounts above the daily caps (C4.2) or the annual limit (C4.3).

---

## C5. When cover starts: waiting period and alert look-ahead

**Waiting period:** Cover starts 7 days after the day you ask for it, never sooner. We pay no claim for a day before the start. This stops people buying cover after they see an alert.

**Alert look-ahead:** When you ask for cover, we check your zone. If an alert for your zone is in force now, or was issued and starts within the next 72 hours, we tell you that the new cover will not apply to that alert (the quote outcome is BLOCKED). You can still buy cover. It starts after the waiting period like any other cover.

**Example:**
- You ask for cover on Monday 18 Aug at 18:00. An alert issued at 17:30 covers your zone for tomorrow.
- We reply: "New cover starts after the waiting period — from 25 August. It won't apply to tomorrow's alert." We also send a payment link for 30 days of premium (₹424.80 in zone Z3).
- Your cover starts on 25 Aug. Claims for days from 25 Aug onwards can be paid, once your premium is prepaid for those days.

---

## C6. Premium and cash before cover

**Premium:** We charge a daily premium. The minimum is ₹2 per day. Your first payment covers 30 days upfront, counted from the day your cover starts. After that, the premium is deducted from your Paytm settlement each evening (standing consent required), when that day's collections are enough to pay it. If they are not, your prepaid days do not move forward.

**Cash before cover:** Under Indian insurance law (Insurance Act 1938, section 64VB), cover for a day starts only when that day's premium is received. Your first payment (the 30-day prepayment) must clear before any claim on those 30 days is paid. After that, each evening's settlement deduction grants cover for the next day. The policy engine checks this on every claim (PREMIUM_PREPAID: the premium is prepaid through the day of the event).

**Premium table:** The premium for each zone is shown with the cover quote (in the chat today; in the merchant mini-app once N1 ships, PLANNED). It is the zone's expected area loss per shop per day ÷ 0.65 (a 35% loading), with a minimum of ₹2 a day. Example: in zone Z3 the premium is ₹14.16 a day, which implies an expected loss of about ₹9.20 a day (₹14.16 × 0.65). Across the 24 zones the premium runs from ₹6.93 to ₹38.82 a day. Hospital-cash is not priced separately yet: the premium is based on area loss only.

---

## C7. What is not covered (exclusions)

We do not cover income loss due to:

1. A shop closure that no RAIN or CIVIC alert for your zone explains. A HEATWAVE alert does not trigger cover.
2. Medical bills. Hospital-cash pays your lost income, not the cost of treatment (use health insurance for that).
3. Damage to your shop or equipment (use a property insurance for that).
4. A supply chain shortage (if you sell goods and your supplier does not deliver).
5. Injury to your customers, or any claim they make against you.
6. An alert that was issued before you bought cover.
7. Hospital admission without a valid slip (we need the document to verify the dates). A slip that is unclear goes to a person for review.
8. Admission to a private clinic or unregistered hospital (proposed: we would accept government and registered private hospitals only; the prototype does not check this).

**Proposed additions (to be finalized with the insurer):**

9. Any claim filed more than 30 days after the event.
10. More than one payout for the same day and the same kind of claim. The engine already enforces this per kind (NOT_ALREADY_PAID). Whether an area payout and a hospital-cash payout for the same day may both be paid is for the insurer to decide.
11. Any claim for which you gave false information on the slip or in the KYC.

---

## C8. How claims are decided and explained

**Area income loss:**
1. The trigger fires at the policy engine (our code that applies the rules).
2. Every merchant in the zone is checked: do you have cover, has your waiting period ended, is your premium paid?
3. If yes, you are paid the amount automatically. A message in Hindi and English tells you the area's drop and the amount credited. Ask "why this amount?" for the formula and your numbers.
4. If no, nothing is paid and the decision records which check failed. Area claims have no merchant-facing "not paid" message yet (proposed).

**Hospital-cash income loss:**
1. Our system detects a silent day (see C1).
2. We message you at 11:20 the next morning, in Hindi and English, asking if you are okay. A voice version is PLANNED (N4).
3. You reply by voice note or tap a button, then send a photo of the hospital slip.
4. We extract the patient name, admission and discharge dates and hospital name.
5. We check these things on the slip and the claim:
   - Does your name on the slip score at least 85 against your KYC name?
   - Do the dates on the slip cover the silent day(s)?
   - Is the slip readable (at least 80% confidence) and a medical document?
   - Is the claim for 3 days or fewer?
6. If all pass, and your cover is in force, you are paid automatically. The explanation shows the formula: half the expected day, the cap and the number of days.
7. If a slip check fails or is unsure, a person (the claims officer) reviews it. You get a message that our team will check it and you will hear back within 24 hours. The tracker with a "waiting for review" step (H1) is PLANNED. If a rule such as cover in force fails, the claim is declined and the reason is given.

**Reproducibility:** Every money number shown to you is reproducible. You can see the formula, the facts used (your expected day, the area index, the drop %, the cap), and the check results in the explanation card.

---

## C9. Disputes and grievances

**If you disagree with a payout:**

1. Tell us in the chat what you think we got wrong (for example "My loss was bigger"). A Dispute button in the claims tracker is PLANNED (H1).
2. A case opens. You see "Sent to a claims officer" with the case number, and we tell you that you will hear back within 24 hours. A "Dispute open" status with a 24-hour clock in the tracker is PLANNED (H1).
3. A claims officer checks the decision's numbers against the rules. The officer either confirms the payout or rejects the dispute, and you are told why. A dispute does not change the amount, and the case is then closed.
4. If you are still unhappy, you can escalate to the insurer's grievance officer, then to IRDAI's Bima Bharosa portal, and finally to the Insurance Ombudsman (free to you). Chhatri's own grievance ladder with response clocks is PLANNED (N5, H22).

**Claims officer review (REFERRED claims):**
- If a slip does not pass the slip checks (name, dates, readability or more than 3 days), a claims officer reviews it. The officer re-runs all the checks and can approve or decline. An approved slip check is recorded as waived by the officer. The other rules (cover in force, premium, annual limit) still apply.
- The officer sees the slip image, the name on the slip, your KYC name, the match score, the silent days and the check results.
- We aim to decide within 24 hours.

---

## C10. EDI holiday: the lender's decision

**What is an EDI holiday?**

An EDI (equated daily instalment) holiday moves one day's loan instalment to the end of the loan. **Your lender decides whether to grant it. Chhatri does not pause your instalment.** After we pay you a claim (area or hospital-cash), Chhatri sends your lender a request, under a rule the lender agreed in advance. The lender grants or refuses.

**The lender's rule (PLANNED, X4):** the lender grants the holiday only if your loan is active, you are not in arrears, you have holiday allowance left and your loan is part of the holiday scheme. Today the prototype's simulated lender has no such check and always grants. Its message, "Tomorrow's ₹600 instalment is paused.", also reads as if Chhatri did it. X4 adds the check and the lender-decides wording below.

**If the lender grants it:**
- Your next instalment moves to the end of your loan tenure.
- You do not pay any penalty.
- You see a message (proposed wording, X4): "Your lender has paused tomorrow's ₹600 instalment. It moves to the end of your loan with no penalty."

**If the lender refuses or does not answer:**
- Your instalment is due as usual. Your payout is not affected.
- You see a message that names the reason (proposed wording, X4): "Your lender could not pause tomorrow's ₹600 instalment: the loan has an amount overdue. It is due as usual. Your payout is not affected."

**Alternative:** The lender's compliance team may prefer that the insurer pays the instalment from the payout (like an EMI-protection cover). Your loan terms then do not change at all.

**Timeline:** In the prototype's replay the payout is credited at 17:04 and the request goes to the lender at 17:05 (simulated time). The lender's answer is shown in the chat. A tracker step for it (H1) is PLANNED.

---

## C11. Your data and consent

**What data we collect:**
- Your sales data (daily totals and hourly buckets during alerts).
- Your Soundbox transactions (for silent-day detection).
- Your hospital slip (patient name, admission and discharge dates, hospital name).
- Your Paytm account data (KYC name, phone number, settlement account).

**Why we collect it:**
- Sales data and Soundbox: to decide area and hospital-cash claims.
- Hospital slip: to verify the admission and match your name.
- KYC and account: to settle the payout.

**Your consent:**
- When you buy cover, you give consent for us to use your sales and Soundbox data for the purpose of deciding claims and calculating premiums.
- When you file a hospital-cash claim, you give consent for us to read and store the slip data for that claim only.
- You can withdraw consent anytime. The consent centre, with a log of what was used and when, is PLANNED (N6, H23). Once you withdraw, we stop collecting new data. Existing data is kept for 7 years for dispute resolution, then deleted.
- For children: cover is only for adults (age ≥ 18). We do not collect data on minors.

**Your rights (under the Digital Personal Data Protection Act, 2023):**
- You can ask us what data we have on you.
- You can ask us to correct wrong data.
- You can ask us to delete your slip data once a claim is closed. A "forget my slip" button is PLANNED (N6, H23). The prototype has no deletion path for slips today.
- You can ask at any time. We aim to respond within 30 days (a proposed target).

---

## C12. Cancellation, renewal and free look (all proposed)

Nothing in this clause is built or set in the rules. The insurer will decide it.

**Free look (proposed):**
- You have 14 days from the start date to cancel for any reason and get a refund of the premium you paid upfront (minus a ₹10 fee for processing).

**Renewal (proposed):**
- Cover is renewed every year. On the renewal date, you are charged the new year's premium (calculated on 31 December for the year ahead).
- We will remind you by phone or WhatsApp 7 days before renewal.

**Cancellation (proposed):**
- You can cancel anytime by tapping "Cancel cover" in the app.
- If you cancel before a claim is fully decided, we keep the premium for the days you had cover.
- If you cancel after a dispute is opened, the dispute is still resolved.

---

## Customer Information Sheet (as per IRDAI format)

| Field | Answer |
|---|---|
| **Product name** | Chhatri — Income cover for small merchants |
| **Insurer** | [Partner general insurer to be named] |
| **Distributor** | [To be named. The plan is Paytm Insurance Broking, an IRDAI-licensed broker (A4). Not agreed.] |
| **Type of cover** | Parametric income-protection insurance (area and hospital-cash) |
| **Coverage** | Automatic payouts for sales losses during RAIN or CIVIC alerts (area) and for silent days with a hospital slip (hospital-cash). No medical underwriting. |
| **Premium** | Minimum ₹2 per day; varies by zone (₹6.93 to ₹38.82 a day in the prototype). First payment covers 30 days from the start date; thereafter daily deduction from settlement. |
| **Waiting period** | Cover starts 7 days after the day you ask for it. No claims are paid before the start date. |
| **Alert look-ahead** | If an alert for your zone is in force now, or starts within 72 hours, new cover will not apply to it. You can still buy cover. It starts after the waiting period. |
| **Claim limits** | Area: up to ₹2,500 per day, per merchant. Hospital-cash: up to ₹1,500 per day, for up to 3 days automatically; then human review. Total limit: ₹30,000 per merchant in any rolling 365-day period. |
| **Payout share** | 50% of the calculated loss. |
| **Claims process** | Area: automatic, no claim form. Hospital-cash: you send a hospital slip; automatic decision if the checks pass, otherwise human review (we aim to answer within 24 hours). |
| **Dispute resolution** | 24-hour SLA for a dispute response. Then grievance ladder: insurer GRO → IRDAI Bima Bharosa → Insurance Ombudsman. |
| **EDI holiday** | Chhatri requests it after a payout. The lender decides. |
| **Cancellation** | Proposed: free look of 14 days with refund (minus ₹10 fee). Anytime after: free cancellation; premium kept for days covered. |
| **Exclusions** | Closures that no RAIN or CIVIC alert explains, HEATWAVE alerts, medical bills, property damage, customer claims, alerts issued before you bought cover, admission without a valid slip. Proposed: claims after 30 days, false information. |
| **Renewal** | Proposed: yearly renewal, set by the insurer. |
| **Contact** | [Insurer GRO and Paytm support to be filled in] |
| **Final CIS** | This CIS is illustrative. The final Customer Information Sheet will be issued by the insurer on the filed and approved product. |

---

## Hindi summary (एक स्क्रीन पर मुख्य शर्तें)

**छत्री — छोटे दुकानदारों के लिए आय बीमा**

| शब्द | मतलब |
|---|---|
| **क्या है** | जब बारिश होती है या आप बीमार हो जाते हैं तो आपकी बिक्री गिर सकती है। हम उस दिन के आधे नुकसान का भुगतान करते हैं। |
| **कितना प्रीमियम** | प्रति दिन कम से कम ₹2। पहले महीने का 30 दिन का प्रीमियम पहले ही दें। फिर हर रात को settlement से काट दिया जाएगा। |
| **कितना मिलेगा** | Area claim: आधे दिन की expected बिक्री × drop %, ₹2,500 तक। Hospital: आधे दिन की expected, ₹1,500 तक, 3 दिन तक। हर साल कुल ₹30,000 तक। |
| **कब से cover** | आप cover खरीदने के 7 दिन बाद से claims पा सकते हैं। |
| **claim कैसे होता है** | Area: अपने आप। Hospital: आप slip भेजते हो, हम देखते हैं, फिर पैसा। |
| **dispute** | असहमत हो? "Dispute" दबाओ। हम 24 घंटे में जवाब देंगे। |
| **EDI holiday** | Area या hospital claim के बाद, हम आपके lender से पूछते हैं कि क्या वह अगले दिन की instalment defer करेगा। lender ही decide करता है। |
| **cancel (प्रस्तावित)** | 14 दिन में बिना कारण के cancel कर सकते हो (₹10 fee के साथ refund)। बाद में भी cancel कर सकते हो। |

---

## Open questions

1. Will the partner insurer provide definitions and exclusions that are more specific to their underwriting appetite? Owner: Omkar Kadam.
2. Is the free-look period (C12 proposed) acceptable, or should it be 7 days? Owner: Omkar Kadam.
3. Should we add an exclusion for "acts of war or terrorism"? Owner: Omkar Kadam.
4. Will the insurer specify a list of accepted hospitals for hospital-cash claims? Owner: Omkar Kadam.
5. What is the timeline for the insurer to file this product (or a variant) with IRDAI? Owner: Omkar Kadam.
6. Should only Red (or Orange and Red) alerts trigger area cover? The prototype accepts a RAIN or CIVIC alert of any colour. Owner: Omkar Kadam.
7. What is the merchant's recourse if the engine itself is wrong? Today a dispute cannot change an amount, so a correction would need a new decision by the insurer. Owner: Ujjwal Pardeshi.

---

## Changelog

- 2026-10-02 · v1.5 · fixed against the code: any RAIN or CIVIC alert triggers (colour unused, HEATWAVE does not); BLOCKED cover can still be bought and starts after 7 days; name, dates, readability and the 3-day limit send a claim to a person (REFERRED), not a decline; disputes do not change amounts; C10 says the lender decides, with proposed wording; expected-day model has no weather input; unbuilt items marked PLANNED or proposed.
- 2026-10-02 · v1.4 · second fact-check pass: correct terminology for slip checks (not "hard checks")
- 2026-10-02 · v1.3 · final consistency pass against the code
- 2026-10-02 · v1.2 · logic and truth audit fixes. Removed Red alert stacking rule (C4.4) and duplicate slip rule (C3) — not yet implemented in policy engine; fs-02 §7.3 and rules.yaml document the authoritative check list.
- 2026-10-02 · v1.1 · fact-check pass. Fixed annual limit clause C4.3 and CIS: now states rolling 365 days (matching code) instead of calendar year.
- 2026-10-02 · v1 · first draft, clause structure C1–C12 aligned with Ask Chhatri (fs-05), CIS and Hindi summary added.
