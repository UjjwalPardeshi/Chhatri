# Personas and jobs to be done

| | |
|---|---|
| Status | Draft v1 · 2 Oct 2026 |
| Owner | Omkar Kadam |
| Audience | Product, design, engineering, judges |
| Related | [Facts and sources](../01-strategy/facts-and-sources.md) · [Metrics and impact](metrics-and-impact.md) · [User journeys](./user-journeys.md) |

## TL;DR

- Five personas: Anil (merchant, primary), Ramesh (underinsured merchant), Priya (roadmap), Rajesh (claims officer), Amit (field executive).
- Each persona is fictional, evidence-informed from merchant data and industry research, and labelled as such.
- The first two personas represent today's customer base. Priya represents the roadmap (heatwave cover in Delhi). Rajesh and Amit represent internal users.
- Jobs to be done guide feature design: "When a monsoon hits, I want the claim to start itself so I can focus on my shop."

## 1. Primary persona: Anil Jadhav

**Role:** Tea-stall owner, Parel (Z7), Mumbai.

**Demographics:** 45 years old, Hindi and Marathi speaker, reads Devanagari but not fluent in English. Married, two teenage children. Phone: Android, 4–5 years old, no home internet.

**Financial profile:** Daily sales ₹800–1,200. Daily merchant EDI: ₹600. Annual net income: ₹1.5–1.8 lakh. Operates on thin margins; a three-day drop in sales forces food cuts or inventory debt.

**Context:** Anil's stall is near a bus terminus in Parel. He bought the Paytm device six years ago. In the monsoon, rainwater floods the street outside, and foot traffic drops 60–70%. A red alert on 18 Aug 2025 forecasts rain; on the day, Anil's shop sits empty. His ₹600 loan repayment is due. He has heard of insurance but never bought it (evidence-informed from merchant lending reports; specific policy data unavailable).

**Goals and frustrations:**

- **Goal:** Protect his income during monsoons and strikes so he can pay the loan and keep stock.
- **Frustration:** Previous claims took 30–60 days and asked for bills, doctor letters, and photos. He does not keep receipts and has no doctor. The claim was denied. He does not trust insurance now (A3).
- **Frustration:** On the day it rains, he cannot leave his shop to visit an agent or call a helpline. A phone call in Hindi is okay; a form is not.

**Devices and channels:** Android phone, no data plan (WiFi at home only). WhatsApp on the Paytm device (via Paytm WiFi or merchant hotspot). Soundbox announcements. He checks the Paytm app once a day, usually evening.

**Accessibility:** Reads Devanagari (Hindi, Marathi). No literacy barrier with images, charts, or simple icons. Voice is his preferred channel (to save data). Colorblind accessibility: not known, but red–green alerts must be supported with text or tone.

**Chhatri features that serve Anil:**

- **K1 Area auto-claim:** On a red alert, if his zone's sales drop below the trigger, he is paid ₹1,380 with no action. The claim "starts itself".
- **N1 Merchant mini-app:** Explains the cover ("What am I covered for?"), tracks the claim ("Detected → Checked → Decided → Paid → EDI holiday"), and shows why he got ₹1,380 (K5).
- **N2 Ask Chhatri:** When Anil asks "मुझे इतने ही पैसे क्यों मिले?" ("Why did I get only this much?"), the LLM gives a grounded answer in Hindi, quoting the policy and the numbers.
- **N4 Hindi voice:** Announcements and responses come by voice and Soundbox, not SMS or push.
- **K3 EDI holiday:** His ₹600 instalment is paused for one day, giving him cash to stock the next morning.

**Day-in-the-life: 19 Aug 2025 (monsoon):**
- 06:00: Opens the stall. Checks the Paytm app; sees a red alert for Z7. Realizes the cover is active (because he bought it on Aug 12).
- 14:00: Sales are zero. The street is flooded. He makes tea for the few neighbours who stop by.
- 17:00: The Soundbox announces "आपके ₹1,380 का भुगतान हो गया" ("Your ₹1,380 has been paid"). Anil checks the Paytm app and sees the money.
- 18:00: The loan repayment (₹600) is due. The Paytm app shows "Instalment paused until tomorrow" and "Chhatri EDI holiday". He keeps the ₹600.
- 06:00 next day: Stocks the stall with leftover flour and supplies before opening.

**Jobs to be done:**

1. When a monsoon hits and my sales collapse, I want the claim to start itself (no form, no call) so I can focus on opening the stall the next day without panic.
2. When I do not understand the payout, I want to ask a question in my language so I can trust the number.
3. When the loan is due the same day, I want the instalment to pause so I can stock the next morning.
4. When I buy cover, I want to know what I am covered for (weather, illness, how much) so I do not waste money.

**Success metric:** Anil is paid on the day of the loss (same day), without calling anyone. He learns the amount by Soundbox and understands why.

**Assumptions to validate in pilot:**

- Merchant adoption: Will Anil buy income cover at zone-specific premium (₹18.62/day for Z7) if it covers monsoons and illness? (Hypothesis: yes, if the claim is same-day and no forms.)
- Accuracy of the area trigger: Does the 50%-drop threshold match Anil's lived experience of a "loss day"? (Hypothesis: yes, but we will measure in the pilot.)
- EDI holiday: Will Anil prefer a one-day holiday over a ₹600 instalment paid from the payout? (Hypothesis: yes, so he has cash to stock the next day.)

---

## 2. Secondary persona: Ramesh

**Role:** Vada Pav vendor, Worli (Z3), Mumbai.

**Demographics:** 38 years old, Hindi and Marathi speaker, basic numeracy, owns one street stall (not registered). Phone: Android, has Paytm on the device, but not yet a merchant account with loans.

**Financial profile:** Daily sales ₹400–600. No formal borrowing; buys stock on credit from a local supplier and pays daily. No savings. Wants to cover inventory risk but has not bought insurance before.

**Context:** Ramesh runs a vada pav stall. He is not yet on Paytm for Business (the merchant lending app) and has no loan. He hears about Chhatri from Anil and considers buying cover during a red alert on 18 Aug 2025, but he is blocked by the 7-day waiting period (K6, 72-hour alert look-ahead). He comes back on 25 Aug, the first day he can buy.

**Goals and frustrations:**

- **Goal:** Protect his inventory and daily sales when a strike or flood stops foot traffic.
- **Frustration:** He has no formal income proof, so banks do not lend to him. He wants insurance but is unsure of the terms.
- **Frustration:** Previous attempts to buy insurance were rejected at the counter for being "too small a business".

**Devices and channels:** Android device, Paytm, WhatsApp. No bank account. Pays in cash.

**Chhatri features that serve Ramesh:**

- **K6 Cover purchase with waiting period:** Ramesh can buy on 25 Aug (after the 7-day wait from 18 Aug). The waiting period blocks opportunistic cover during an active alert but protects the pool from selection bias.
- **N1 Consent and buy:** Ramesh taps "Buy cover", sees 30 days of Z3 premium (₹424.80, about ₹14 a day), and buys via a Paytm link (SIMULATED in the demo, real staging link in the pilot).
- **N1 Coverage explainer:** Ramesh reads "What am I covered for?" and sees examples, exclusions, and caps in Hindi.

**Day-in-the-life: 18 Aug 2025 (red alert):**
- Morning: Ramesh asks Anil if he can buy cover. Anil says yes but mentions a waiting period.
- Afternoon: Ramesh opens Chhatri in the Paytm app and taps "Buy cover". The mini-app says "Cover cannot start until 25 Aug. A red alert is active until 20 Aug; we block cover during alerts to protect everyone."

**Day-in-the-life: 25 Aug 2025 (cover purchase):**
- Ramesh buys 30 days of cover. He is shown the premium (₹14.16 a day) and taps "Confirm". A Paytm link opens. He pays via Soundbox or merchant device. Cover starts.

**Jobs to be done:**

1. When a red alert is coming, I want to buy cover but not during the alert so the insurer trusts the pool.
2. When I buy, I want to see the price upfront and know what I am covered for so I decide quickly.
3. When a flood hits, I want to be paid like Anil, with no forms.

**Success metric:** Ramesh buys cover within 3 days of the waiting period ending and is paid on the first loss day after purchase.

---

## 3. Roadmap persona: Priya

**Role:** Kirana shop owner, South Delhi.

**Demographics:** 40 years old, Hindi speaker, married, two school-age children. Phone: Android, uses WhatsApp frequently.

**Context:** Priya runs a small grocery store in Delhi. The summers are hotter each year. A heatwave in April 2025 saw temperatures over 48°C for a week; her sales dropped 50% because customers stayed home and bought essentials only. She lost ₹800 that week.

**Goals:** Protect her income during extreme heat, which is now a recurring monsoon-like crisis.

**Chhatri features (H3 roadmap):**

- **Area Income Signal (roadmap, ROADMAP):** Paytm's hourly sales index for Delhi zones, available to lenders and insurers. Priya's zone goes offline as foot traffic stops. The trigger fires.
- **Heatwave cover (roadmap, ROADMAP):** Like monsoon cover, but for IMD orange or red heat alerts. Payment rules are the same: 50% of expected sales drop.
- **Marathi support (N8, H3):** While Priya speaks Hindi, many Delhi merchants speak Marathi, Punjabi, or Urdu. H3 roadmap adds these languages.

**Why Priya is not in H0:** Heat-index data requires a longer calibration (several hot seasons) and a separate trigger design. The hackathon focuses on monsoon (K1) and illness (K2). Priya's story is the motivation for H3 scale.

---

## 4. Internal persona: Rajesh

**Role:** Claims officer at the partner insurer.

**Demographics:** 35 years old, experienced in health and personal-accident claims. Office-based in Mumbai.

**Context:** Rajesh works for the partner insurer and reviews Chhatri claims that the algorithm marked REFERRED (unclear slip, name mismatch, or ambiguous dates). He uses the claims-officer console (K8) on a desktop.

**Goals:**

- Decide referred claims accurately and quickly (target 24-hour SLA per K5).
- Understand why the algorithm flagged the case (confidence scores, name-match percentage, missing fields).
- Approve or reject with an explanation that the merchant sees in Hindi.

**Chhatri features that serve Rajesh:**

- **K8 Claims-officer console:** A queue of open cases, each showing the slip, the extracted fields, the algorithm's confidence, the merchant's KYC, and the decision history.
- **K5 Explanations and disputes:** When Rajesh approves a case, the explanation is auto-generated and shown to the merchant.
- **K7 Audit log:** Every decision is logged with a hash chain and a timestamp, so Rajesh's review is auditable.

**Success metric:** Rajesh resolves 95% of REFERRED claims within 4 hours (well ahead of the 24-hour SLA). The merchant's approval message is clear.

---

## 5. Internal persona: Amit

**Role:** Paytm field sales and relationship executive, Mumbai.

**Demographics:** 32 years old, Hindi and English speaker, travels across Mumbai, visits merchants weekly.

**Context:** Amit onboards merchants, explains Paytm's offerings (lending, payments, insurance), and builds relationships with shop owners. With Chhatri, he has a new product to explain.

**Goals:**

- Help merchants understand Chhatri's cover, premium, and claims process in simple Hindi.
- Drive adoption in his assigned zone.
- Answer merchants' questions accurately without a script.

**Chhatri features that serve Amit:**

- **Ask Chhatri (N2):** Amit can ask the system "What do I tell a merchant who is worried about a 7-day waiting period?" and get a grounded answer.
- **Coverage explainer (N1):** Amit can show Priya the mini-app screen "What am I covered for?" to explain the policy.
- **Receipt and explanation (K5, H3):** Amit can show a past payout receipt to a new merchant to build confidence.

**Success metric:** Amit explains Chhatri to 10 new merchants in a week, and 7 of them buy within a month.

---

## 6. Anti-personas (who Chhatri is not for)

- **High-volume traders with sophisticated insurance.** A large grocery chain with a CFO and a broker will negotiate a custom business interruption policy. Chhatri is parametric and non-negotiable.
- **Risk-averse insurers who dislike parametric products.** An insurer nervous about basis risk (merchants paid when it did not rain) will not adopt. This is a known trade-off; we accept it to get same-day payouts.
- **Merchants outside Paytm's device network.** Chhatri lives inside Paytm; it needs live sales data and settlement rail access. A merchant using Square or Razorpay is not served.

---

## 7. Accessibility needs

- **Language:** Devanagari fluency required. English is optional. Marathi (roadmap) needed for Mumbai and surrounding areas.
- **Vision:** High contrast for red-green colorblind users. Zone alerts must use text or tone, not colour alone.
- **Literacy:** Messages avoid complex financial jargon. Numbers are shown with rupee symbol (₹). Icons are labelled.
- **Data:** Voice (N4) is primary; text is fallback. This saves mobile data for merchants with limited plans.
- **Hearing:** Soundbox announcements are text-on-screen for deaf users. Chat and WhatsApp are text-first alternatives.

---

## 8. Assumptions to validate in pilot

1. **Merchant adoption:** Will more than 30% of merchants in the pilot zone buy Chhatri at the pilot price (the backtest gives ₹18.62 a day in Z7; the price is open)? (Hypothesis: yes, if trust in same-day claims is demonstrated.)
2. **Claim accuracy:** Will the area trigger's 50% threshold match merchants' lived experience of "significant loss"? (Hypothesis: yes, with a ±10% tolerance.)
3. **EDI holiday preference:** Do merchants prefer a one-day loan pause to a ₹600 instalment credit? (Hypothesis: yes, because it keeps their cash available for next-day restocking.)
4. **Dispute rate:** What is the dispute rate after Chhatri's explanation is shown? (Hypothesis: less than 5%, compared to typical insurance 10–15%.)
5. **Lender confidence:** Will a lender partner accept Chhatri's EDI holiday decision? (Hypothesis: yes, because it is pre-agreed and credible via Paytm's settlement control.)

---

## 9. Personas and the product roadmap

| Persona | H0 (final) | H1 (shadow) | H2 (pilot) | H3 (scale) |
|---|---|---|---|---|
| **Anil** (primary merchant) | Buy, claim monsoon, track, ask | Grieve | Live pilot (real rain) | Same-day payouts proven; renewed |
| **Ramesh** (secondary) | Buy with waiting period | — | First buy during waiting period | — |
| **Priya** (heatwave) | Story only | Story only | — | Heatwave cover, Delhi |
| **Rajesh** (officer) | Review referred | Improve SLA | Live cases | Operational scale |
| **Amit** (field) | Train on features | Support merchants | Onboarding stories | Regional expansion |

---

## Open questions

1. Is the 50% area-trigger threshold accurate to merchants' lived experience? Owner: Ujjwal Pardeshi.
2. What is the dispute rate in a real pilot, and how does it compare to health insurance (8% repudiation A10)? Owner: Ujjwal Pardeshi.
3. Will a lender accept the EDI holiday as designed, or will they insist on a different alternative (e.g. paying the instalment from the payout)? Owner: Omkar Kadam.

## Changelog

- 2026-10-02 · v2 · final consistency pass against the code
- 2026-10-02 · v1 · first draft.
