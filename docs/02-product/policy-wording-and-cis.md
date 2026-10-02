# Policy wording and Customer Information Sheet

| | |
|---|---|
| Status | Draft v1 · 2 Oct 2026 |
| Owner | Omkar Kadam |
| Audience | Insurer partners, legal and compliance counsel, judges |
| Related | [Regulatory and compliance](../05-business/regulatory-and-compliance.md) · [Facts and sources](../01-strategy/facts-and-sources.md) · [Feature specs](feature-specs/fs-01-area-auto-claim.md) |

## TL;DR

- This is an **illustrative draft for the hackathon only**. It is not a filed or approved product. The partner insurer will write the real policy wording.
- Clause IDs C1–C12 are stable and cited by Ask Chhatri (fs-05).
- Wording follows rules.yaml pilot-0.1: 50% payout share, area cap ₹2,500 a day, hospital-cash cap ₹1,500 a day (up to 3 automatic days), annual limit ₹30,000, 7-day waiting period, 24-hour dispute SLA.
- Covers area income loss (alert-triggered) and hospital-cash income (slip-based). Payouts are settled the same day.
- A Customer Information Sheet (as a table) and a one-screen Hindi summary complete the document.

---

## C1. Definitions

**Alert:** An IMD colour-coded warning (Red alert: "take action") issued for a zone. Chhatri receives alerts from the weather service and notifies covered merchants in the zone.

**Area income loss:** A loss of merchant sales when the sales index (the average sale per shop in the zone relative to expected) falls below 50% for 3 consecutive hours during an alert, and is also below the AI model's lower confidence bound.

**Area sales index:** The average daily sales per shop in a zone, expressed as a percentage of the expected sales for that day. At least 20 shops must be in the index for a valid trigger.

**Expected day:** The AI-predicted median sales for a merchant on a given date, based on historical patterns, trained on the merchant's own sales and local weather. The payout is calculated as half the expected day × the percentage drop.

**Hospital slip:** A document from a hospital (admission proof, discharge summary or hospital ID) showing the patient name, admission and discharge dates, hospital name and the nature of admission (e.g. "Viral fever").

**KYC name:** The legal name registered when the merchant's Paytm account was opened and verified.

**Silent day:** A full calendar day (00:00–23:59 in the merchant's local timezone) on which the merchant's Soundbox recorded zero transactions.

**EDI (equated daily instalment) holiday:** A request by Chhatri for the lender to defer the next day's loan instalment based on the insured event. Whether the lender grants it is the lender's decision under its board-approved policy.

**Settlement:** The daily transfer of the payout amount to the merchant's Paytm wallet or bank account, typically within 4 minutes of the decision.

**Drop:** The percentage of expected sales lost (100% − area sales index %) on the day of the alert.

---

## C2. Coverage: Area income loss

**What we cover.**
- When a Red alert is issued for a zone and you are a covered merchant in that zone, we monitor the area sales index hourly.
- If the index falls below 50% for 3 consecutive hours and is also below our AI model's lower bound for that day, the area income loss claim is triggered automatically. You do not need to do anything.
- You are paid half your expected day's sales × the drop percentage, up to a daily cap of ₹2,500 per merchant.

**Example:**
- You are a tea stall owner in Parel, Zone Z7, with an expected daily sales of ₹4,380.
- On 19 August at 17:00, a Red alert covers your zone. The area index is 37% (down 63%).
- Your payout = 50% × ₹4,380 × 63% = ₹1,380. You receive it the same day.

**When we do not cover area income loss:**
- The alert is not Red, or does not cover your zone.
- The area index does not fall below 50% or does not stay there for 3 hours.
- You do not have cover on the day of the alert, or your waiting period (7 days) is still running.

---

## C3. Coverage: Hospital-cash income loss

**What we cover.**
- If you are admitted to a hospital and the Soundbox records zero sales that day, we check in with you by voice.
- You send one photo of a hospital document (admission proof, discharge summary or hospital ID).
- If the slip shows your name (≥ 85% match with your KYC name), the dates match the silent days, and the slip is readable (≥ 80% confidence), we approve your claim automatically.
- You are paid half your expected day's sales, up to ₹1,500 per day, for up to 3 days automatically. After 3 days, a person reviews the claim.
- You receive the money the same day.

**Example:**
- You were admitted to KEM Hospital on 20 August with a viral fever. The Soundbox shows zero sales.
- On 21 August at 11:20, we call and you reply by voice, then send a photo of your discharge slip.
- Your name on the slip matches your KYC at 92%. We approve ₹1,500 (half of ₹4,300 expected, capped at ₹1,500 × 1 day).

**When we do not cover hospital-cash:**
- Your name on the slip does not match your KYC at 85% or higher.
- The slip does not show the dates of your silent day(s).
- You do not have cover, or your waiting period is still running.
- The dates on the slip fall outside your cover period.

---

## C4. How much we pay

### C4.1 Payout formula

Payout = **50% × Expected day × Drop %**, subject to daily and annual caps.

- **Expected day:** The AI-predicted median sales for you on that day, from your own sales history and local weather.
- **Drop %:** (100% − area sales index) for area claims; 100% for hospital-cash (we assume the full day was lost).
- **Payout share:** We cover 50% of the loss; the other 50% is your deductible.

### C4.2 Daily caps

- **Area income loss:** Maximum ₹2,500 per merchant per day.
- **Hospital-cash income loss:** Maximum ₹1,500 per merchant per day, for up to 3 days automatically. Beyond 3 days, a person reviews.

### C4.3 Annual limit

The total payout across all claims (area and hospital-cash) cannot exceed ₹30,000 per merchant in any rolling 365-day period.

### C4.4 What we do not pay

- Payouts below ₹1 (rounding).
- Claims outside your cover period.
- Claims before your 7-day waiting period ends.

---

## C5. When cover starts: waiting period and alert look-ahead

**Waiting period:** After you buy cover, we do not pay any claim for 7 days. This is to prevent abuse.

**Alert look-ahead:** If a Red alert is forecast for your zone within the next 72 hours, you cannot buy cover or change your cover during that window. For example, if a Red alert is expected on Wednesday, you cannot buy cover on Monday or Tuesday.

**Example:**
- You buy cover on Monday 18 Aug at 18:00. A Red alert is forecast for Wednesday 20 Aug.
- You cannot change or cancel your cover until the alert ends. Your waiting period expires on Monday 25 Aug at 18:00.
- Claims are paid from 25 Aug onwards.

---

## C6. Premium and cash before cover

**Premium:** We charge a daily premium. The minimum is ₹2 per day. Your first payment covers 30 days upfront. After that, the premium is deducted from your Paytm settlement each evening (standing consent required).

**Cash before cover:** Under Indian insurance law (Insurance Act 1938, section 64VB), cover for a day starts only when that day's premium is received. Your first payment (the 30-day prepayment) must clear before any claim on those 30 days is paid. After that, each evening's settlement deduction grants cover for the next day.

**Premium table:** Premium for each zone is published in the merchant mini-app. It is calculated as expected loss for that zone ÷ 0.65. Example: in zone Z3 the expected loss works out to about ₹9.20 a day, so the premium is ₹14.16 a day (₹9.20 ÷ 0.65). The minimum is ₹2 a day.

---

## C7. What is not covered (exclusions)

We do not cover income loss due to:

1. A lockdown or government order that closes your shop (we cover weather only).
2. Your own personal illness or injury (use a personal health insurance for that).
3. Damage to your shop or equipment (use a property insurance for that).
4. A supply chain shortage (if you sell goods and your supplier does not deliver).
5. Accidents or injury to you or your customers (covered by accident or health insurance).
6. Any alert other than Red.
7. Hospital admission without a valid slip (we need the document to verify the dates).
8. Admission to a private clinic or unregistered hospital (we accept government and registered private hospitals only).

**Proposed additions (to be finalized with the insurer):**

9. Any claim filed more than 30 days after the event.
10. More than one claim per calendar day (to prevent double-claiming across different events).
11. Any claim for which you gave false information on the slip or in the KYC.

---

## C8. How claims are decided and explained

**Area income loss:**
1. The trigger fires at the policy engine (our code that applies the rules).
2. Every merchant in the zone is checked: do you have cover, has your waiting period ended, is your premium paid?
3. If yes, you are paid the amount automatically. A message is sent in Hindi and English explaining the payout, the drop percentage, and your caps used this year.
4. If no, we send a message saying why you were not paid (e.g. "Your waiting period runs until 25 Aug").

**Hospital-cash income loss:**
1. Our system detects zero sales (silent day).
2. We send you a voice check-in in Hindi, asking if you are okay.
3. You reply by voice or tap a button, then send a photo of the hospital slip.
4. We extract the patient name, admission and discharge dates and hospital name.
5. We check three things on the slip:
   - Does your name on the slip match your KYC name at 85% or higher?
   - Do the dates on the slip cover the silent day(s)?
   - Is the slip readable (≥ 80% confidence)?
6. If all three pass, you are paid automatically. A message shows the breakdown: expected day, number of days, the cap applied, and a link to the explanation.
7. If any check is borderline or fails, a person (the claims officer) reviews it. You see "Waiting for review" in your tracker, and we aim to decide within 24 hours.

**Reproducibility:** Every money number shown to you is reproducible. You can see the formula, the facts used (your expected day, the area index, the drop %, the cap), and the check results in the explanation card.

---

## C9. Disputes and grievances

**If you disagree with a payout:**

1. Tap "Dispute" in the claims tracker. Tell us what you think we got wrong.
2. You see a "Dispute open" status with a 24-hour clock. We aim to respond within 24 hours.
3. We re-check the numbers. If we find an error, we correct it. If we made a mistake, we send you the extra money. If the numbers are correct, we explain why.
4. If you are still unhappy, you can escalate to the insurer's grievance officer, then to IRDAI's Bima Bharosa portal, and finally to the Insurance Ombudsman (free to you).

**Claims officer review (REFERRED claims):**
- If a slip does not quite pass the automatic checks, a claims officer reviews it. The officer applies the same rules and can approve or decline.
- The officer can see all the information you provided and can ask for more details if needed.
- We aim to decide within 24 hours.

---

## C10. EDI holiday: The lender's decision

**What is an EDI holiday?**

After we pay you a claim (area or hospital-cash), we ask your lender if it will defer your next day's loan instalment (your daily EMI or repayment). The lender decides based on its own policy: is your loan active, are you not in arrears, do you have allowance left for holidays this year, and have you opted in?

**If the lender says yes:**
- Your next day's instalment moves to the end of your loan tenure.
- You do not pay any penalty.
- You see a message saying "Your ₹600 instalment is paused until the end of your loan".

**If the lender says no:**
- Your instalment is due as usual.
- You see a message saying "Your instalment is not paused. Please pay on time".

**Alternative:** Some lenders may choose to have us pay the instalment directly from the payout (like an EMI-protection cover). In that case, your loan terms do not change at all.

**Timeline:** If you are paid at 17:04, the EDI holiday request goes to the lender at 17:05. You see the lender's decision in your tracker the same day.

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
- You can withdraw consent anytime in the consent centre. Once you withdraw, we stop collecting new data. Existing data is kept for 7 years for dispute resolution, then deleted.
- For children: cover is only for adults (age ≥ 18). We do not collect data on minors.

**Your rights (under the Digital Personal Data Protection Act, 2023):**
- You can ask us what data we have on you.
- You can ask us to correct wrong data.
- You can ask us to delete your slip data (after a claim is closed).
- You must ask within 30 days of the decision. We aim to respond within 30 days.

---

## C12. Cancellation, renewal and free look

**Free look (proposed):**
- You have 14 days from the start date to cancel for any reason and get a refund of the premium you paid upfront (minus a ₹10 fee for processing).

**Renewal:**
- Cover is renewed every year. On the renewal date, you are charged the new year's premium (calculated on 31 December for the year ahead).
- We will remind you by phone or WhatsApp 7 days before renewal.

**Cancellation:**
- You can cancel anytime by tapping "Cancel cover" in the app.
- If you cancel before a claim is fully decided, we keep the premium for the days you had cover.
- If you cancel after a dispute is opened, the dispute is still resolved.

---

## Customer Information Sheet (as per IRDAI format)

| Field | Answer |
|---|---|
| **Product name** | Chhatri — Income cover for small merchants |
| **Insurer** | [Partner general insurer to be named] |
| **Distributor** | Paytm Insurance Broking Pvt Ltd (IRDAI Broker Licence) |
| **Type of cover** | Parametric income-protection insurance (area and hospital-cash) |
| **Coverage** | Automatic payouts for sales losses during weather alerts (area) and for hospital-admitted silent days (hospital-cash). No medical underwriting. |
| **Premium** | Minimum ₹2 per day; varies by zone. First payment covers 30 days; thereafter daily deduction from settlement. |
| **Waiting period** | 7 days from the start date. No claims paid during the waiting period. |
| **Alert look-ahead** | If a Red alert is forecast within 72 hours, you cannot buy or change cover. |
| **Claim limits** | Area: up to ₹2,500 per day, per merchant. Hospital-cash: up to ₹1,500 per day, for up to 3 days automatically; then human review. Total limit: ₹30,000 per merchant in any rolling 365-day period. |
| **Payout share** | 50% of the calculated loss. |
| **Claims process** | Area: automatic, decision within minutes. Hospital-cash: you send a hospital slip; automatic decision if the check passes, otherwise human review within 24 hours. |
| **Dispute resolution** | 24-hour SLA for a dispute response. Then grievance ladder: insurer GRO → IRDAI Bima Bharosa → Insurance Ombudsman. |
| **Cancellation** | Free look: 14 days with refund (minus ₹10 fee). Anytime after: free cancellation; premium kept for days covered. |
| **Exclusions** | Lockdowns, non-Red alerts, non-hospital admissions, property or accident claims, claims after 30 days, duplicate claims, false information. |
| **Renewal** | Automatic every year. Premium charged on 31 December for the year ahead. |
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
| **cancel** | 14 दिन में बिना कारण के cancel कर सकते हो (₹10 fee के साथ refund)। बाद में भी cancel कर सकते हो। |

---

## Open questions

1. Will the partner insurer provide definitions and exclusions that are more specific to their underwriting appetite? Owner: Omkar Kadam.
2. Is the free-look period (C12 proposed) acceptable, or should it be 7 days? Owner: Omkar Kadam.
3. Should we add an exclusion for "acts of war or terrorism"? Owner: Omkar Kadam.
4. Will the insurer specify a list of accepted hospitals for hospital-cash claims? Owner: Omkar Kadam.
5. What is the timeline for the insurer to file this product (or a variant) with IRDAI? Owner: Omkar Kadam.

---

## Changelog

- 2026-10-02 · v1.4 · second fact-check pass: correct terminology for slip checks (not "hard checks")
- 2026-10-02 · v1.3 · final consistency pass against the code
- 2026-10-02 · v1.2 · logic and truth audit fixes. Removed Red alert stacking rule (C4.4) and duplicate slip rule (C3) — not yet implemented in policy engine; fs-02 §7.3 and rules.yaml document the authoritative check list.
- 2026-10-02 · v1.1 · fact-check pass. Fixed annual limit clause C4.3 and CIS: now states rolling 365 days (matching code) instead of calendar year.
- 2026-10-02 · v1 · first draft, clause structure C1–C12 aligned with Ask Chhatri (fs-05), CIS and Hindi summary added.
