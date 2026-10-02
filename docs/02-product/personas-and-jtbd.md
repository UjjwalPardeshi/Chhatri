# Personas and jobs to be done

| | |
|---|---|
| Status | Draft v2.1 · 2 Oct 2026 |
| Owner | Omkar Kadam |
| Audience | Product, design, engineering, judges |
| Related | [Facts and sources](../01-strategy/facts-and-sources.md) · [Metrics and impact](metrics-and-impact.md) · [User journeys](./user-journeys.md) |

## TL;DR

- Five personas: Anil (merchant, primary), Ramesh (merchant without cover), Priya (roadmap), Rajesh (claims officer), Amit (field executive).
- Each persona is fictional and labelled as such. Anil and Ramesh are the two demo merchants (S-0142 and S-0907) in a simulated city. Their stories are synthetic scenarios, not real people. The numbers in their profiles come from the simulated data and the demo, not from interviews.
- The first two personas represent the merchant side of the demo. Priya represents the roadmap (heatwave cover in Delhi). Rajesh and Amit represent internal users.
- Jobs to be done guide feature design: "When a monsoon hits, I want the claim to start itself so I can focus on my shop."
- Every N, X and H feature named here is P0 for the 3 Oct final and is built in waves behind feature flags (see the [build plan](../06-delivery/build-plan.md)). Each is marked PLANNED with its wave until it is built. K1 to K8 are BUILT.

## 1. Primary persona: Anil Jadhav

**Role:** Tea-stall owner, Parel (Z7), Mumbai.

**Demographics:** 45 years old, Hindi and Marathi speaker, reads Devanagari but not fluent in English. Married, two teenage children. Phone: Android, 4–5 years old, no home internet.

**Financial profile:** A usual day brings about ₹4,300 in sales (his usual Tuesday is ₹4,380 and his usual Wednesday ₹4,300 in the demo data). Daily loan instalment (EDI): ₹600, about 14% of a usual day. Operates on thin margins; a three-day drop in sales forces food cuts or inventory debt.

**Context:** Anil's stall is near a bus terminus in Parel. In the monsoon, rainwater floods the street outside and foot traffic falls. A red rain alert for his zone was issued on 18 Aug 2025 at 17:30 and is valid from 14:00 to 20:00 the next day. On 19 Aug the sales of Z7 fall to 37% of expected (a 63% drop). His ₹600 loan instalment is still due. In the demo data he bought cover on 10 Mar 2025.

**Goals and frustrations:**

- **Goal:** Protect his income during monsoons and strikes so he can pay the loan and keep stock.
- **Frustration:** Previous claims took 30–60 days and asked for bills, doctor letters, and photos. He does not keep receipts and has no doctor. The claim was denied. He does not trust insurance now (A3).
- **Frustration:** On the day it rains, he cannot leave his shop to visit an agent or call a helpline. A phone call in Hindi is okay; a form is not.

**Devices and channels:** Android phone, no data plan (WiFi at home only). WhatsApp on the Paytm device (via Paytm WiFi or merchant hotspot). Soundbox announcements. He checks the Paytm app once a day, usually evening.

**Accessibility:** Reads Devanagari (Hindi, Marathi). No literacy barrier with images, charts, or simple icons. Voice is his preferred channel. Colorblind accessibility: not known, but red–green alerts must be supported with text or tone.

**Chhatri features that serve Anil:**

- **K1 Area auto-claim (BUILT):** On a RAIN or CIVIC alert, if his zone's sales drop below the trigger, he is paid ₹1,380 with no action. The claim "starts itself".
- **N1 Merchant mini-app (PLANNED, Wave 1):** Explains the cover ("What am I covered for?"), tracks the claim ("Detected → Checked → Decided → Paid → EDI holiday"), and shows why he got ₹1,380 with the source of every number (K5 is BUILT; H2, H13).
- **N2 Ask Chhatri (PLANNED, Wave 2):** When Anil asks "मुझे इतने ही पैसे क्यों मिले?" ("Why did I get only this much?"), the reply states the numbers from the engine's decision facts. Today the BUILT K5 chat reply already says "Your usual Tuesday: ₹4,380. Your area fell 63%. Chhatri pays half the lost sales."
- **N4 Hindi voice (PLANNED, Wave 2):** Replies can be spoken (Sarvam Bulbul when keyed). Today the Soundbox line is a simulated line in the console.
- **K3 EDI holiday request (BUILT, lender-decides wording PLANNED, X4, Wave 1):** After the payout, Chhatri asks his lender to move the next ₹600 instalment to the end of the loan. The lender decides. Today the simulated lender always agrees.

**Day-in-the-life: 19 Aug 2025 (monsoon).** A synthetic scenario from the demo data, not a real merchant.
- 06:00: Opens the stall. The red alert for his zone was issued yesterday at 17:30 and starts at 14:00.
- 14:00 to 17:00: The street is flooded. Z7's sales stay well below normal for three hours. He makes tea for the few neighbours who stop by.
- 17:00: The area index for Z7 is 37% (down 63%). The policy engine pays every covered shop in the zone. Nobody files anything.
- 17:04: The payout is credited with the settlement. The Soundbox line reads "Paytm par ₹1,380 prapt hue — Chhatri se". His phone shows "Anil ji, heavy rain cut your area's sales by 63% today." (Hindi and English).
- 17:05: Chhatri asks his lender about tomorrow's ₹600 instalment. In today's prototype the simulated lender always agrees and the message reads "Tomorrow's ₹600 instalment is paused." With X4 the message will say that his lender paused it, or why it could not.
- 06:00 next day: If the lender agreed, he has tomorrow's ₹600 for stock before opening.

**Jobs to be done:**

1. When a monsoon hits and my sales collapse, I want the claim to start itself (no form, no call) so I can focus on opening the stall the next day without panic.
2. When I do not understand the payout, I want to ask a question in my language so I can trust the number.
3. When the loan is due the same day, I want my lender to move the instalment so I can stock the next morning.
4. When I buy cover, I want to know what I am covered for (weather, illness, how much) so I do not waste money.

**Success metric (target, not measured):** Anil is paid on the day of the loss (same day), without calling anyone. He learns the amount by Soundbox and understands why.

**Assumptions to validate in pilot:**

- Merchant adoption: Will Anil buy income cover at zone-specific premium (₹18.62/day for Z7) if it covers monsoons and illness? (Hypothesis: yes, if the claim is same-day and no forms.)
- Accuracy of the area trigger: Does the 50%-drop threshold match Anil's lived experience of a "loss day"? (Hypothesis: yes, but we will measure in the pilot.)
- EDI holiday: Will Anil prefer a one-day holiday granted by his lender over a ₹600 instalment paid from the payout? (Hypothesis: yes, so he has cash to stock the next day.)

---

## 2. Secondary persona: Ramesh

**Role:** Vada Pav vendor, Worli (Z3), Mumbai. Demo merchant S-0907, not covered.

**Demographics:** 38 years old, Hindi and Marathi speaker, basic numeracy, owns one street stall (not registered). Phone: Android, has Paytm on the device, but no loan.

**Financial profile:** A street-food stall in the simulated city sells about ₹6,000 on a typical day (the base day for that shop type in the simulation). No formal borrowing; buys stock on credit from a local supplier and pays daily. No savings. Wants to cover inventory risk but has not bought insurance before.

**Context:** Ramesh runs a vada pav stall. He has no loan. He hears about Chhatri from Anil and asks to buy cover on the evening of 18 Aug 2025, after the red alert for his zone has been issued for the next day. Chhatri tells him that new cover starts after the 7-day waiting period, from 25 August, and will not apply to tomorrow's alert (K6, quote outcome BLOCKED). The payment link is still offered. If he pays, his cover starts on 25 Aug.

**Goals and frustrations:**

- **Goal:** Protect his inventory and daily sales when a strike or flood stops foot traffic.
- **Frustration:** He has no formal income proof, so banks do not lend to him. He wants insurance but is unsure of the terms.
- **Frustration:** Previous attempts to buy insurance were rejected at the counter for being "too small a business".

**Devices and channels:** Android device, Paytm, WhatsApp.

**Chhatri features that serve Ramesh:**

- **K6 Cover purchase with waiting period (BUILT):** Cover always starts 7 days after the request. If an alert for his zone is valid now or starts within 72 hours, the quote says BLOCKED: the new cover will not apply to that alert. The link is still offered. The waiting period stops people buying cover after they see an alert.
- **N1 Consent and buy (PLANNED, Wave 1; consent centre N6, Wave 3):** Ramesh taps "Buy cover", sees 30 days of Z3 premium (₹424.80, ₹14.16 a day), and pays through a Paytm link. The link is SIMULATED, because the team has no Paytm keys.
- **N1 Coverage explainer (PLANNED, Wave 1):** Ramesh reads "What am I covered for?" and sees examples, exclusions, and caps in Hindi, with plain-language terms (H20).

**Day-in-the-life: 18 Aug 2025 (alert issued for tomorrow).** A synthetic scenario from the demo data.
- Morning: Ramesh asks Anil if he can buy cover. Anil says yes but mentions a waiting period.
- 18:00: Ramesh asks Chhatri for cover. The reply is "New cover starts after the waiting period — from 25 August. It won't apply to tomorrow's alert." A second message offers the payment link: "To buy cover for later, pay ₹424.80 (₹14.16/day) here: …".
- If he pays, cover starts on 25 Aug and claims for days from then on can be paid.

**Jobs to be done:**

1. When an alert is coming and I ask for cover, I want to be told plainly when it starts, so I am not surprised that tomorrow is not covered.
2. When I buy, I want to see the price upfront and know what I am covered for so I decide quickly.
3. When a flood hits after my cover starts, I want to be paid like Anil, with no forms.

**Success metric (target for a pilot, not measured):** Ramesh understands from one message that cover starts on 25 Aug and that tomorrow's alert is not covered, and pays the link.

---

## 3. Roadmap persona: Priya

**Role:** Kirana shop owner, South Delhi.

**Demographics:** 40 years old, Hindi speaker, married, two school-age children. Phone: Android, uses WhatsApp frequently.

**Context:** Priya runs a small grocery store in Delhi. In a severe heatwave week customers stay home and buy essentials only, so her sales fall. This is an illustrative story. We have no Delhi data and no figures for it.

**Goals:** Protect her income during extreme heat, a recurring crisis like the monsoon.

**Chhatri features (Horizon 3 roadmap, none built):**

- **Area Income Signal (roadmap):** Paytm's hourly sales index for Delhi zones, available to lenders and insurers. Priya's zone goes quiet as foot traffic stops. The trigger fires.
- **Heatwave cover (roadmap):** Like monsoon cover, but for heat alerts. The same payout rule would apply: half the expected sales lost. A HEATWAVE alert kind exists in the data model, but it does not trigger cover today.
- **More languages (roadmap):** Hindi and English work today. Marathi is PLANNED (N8, Wave 4) for Mumbai merchants. Other languages are roadmap.

**Why Priya is not in Horizon 0:** Heat data needs a longer calibration (several hot seasons) and a separate trigger design. The hackathon focuses on monsoon (K1) and illness (K2). Priya's story is the motivation for Horizon 3.

---

## 4. Internal persona: Rajesh

**Role:** Claims officer at the partner insurer.

**Demographics:** 35 years old, experienced in health and personal-accident claims. Office-based in Mumbai.

**Context:** Rajesh works for the partner insurer and reviews two kinds of case in the claims-officer console (K8) on a desktop. A REFERRED claim is one the engine could not pay on its own (unclear slip, name that does not match, dates that do not cover the silent days, or more than 3 days). A DISPUTE is a merchant's challenge to a payout, such as "My loss was bigger".

**Goals:**

- Decide referred claims accurately and quickly (target: answer within the 24 hours the merchant was promised).
- Understand why the algorithm flagged the case (confidence scores, name-match score, missing fields).
- Approve or decline a referred claim, or confirm a payout or reject a dispute, with a reason the merchant sees in Hindi and English.

**Chhatri features that serve Rajesh:**

- **K8 Claims-officer console (BUILT):** A queue of open cases, each showing the slip image, the extracted name, the KYC name, the match score, the silent days and the checks.
- **K5 Explanations and disputes (BUILT):** When Rajesh approves a referred claim, the engine re-runs every check and pays; any SOFT check he approves is recorded as WAIVED_BY_OFFICER, and a HARD fail still declines. A dispute never changes the amount: he confirms the payout or rejects the dispute, and the case is closed.
- **K7 Audit log (BUILT):** Every decision is logged with a hash chain and a timestamp, so Rajesh's review is auditable.

**Success metric (target, not measured):** Rajesh answers 95% of cases within 4 hours, well ahead of the 24-hour promise. The merchant's message is clear.

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

- **Ask Chhatri (N2, PLANNED, Wave 2):** Amit can ask the system "What do I tell a merchant who is worried about a 7-day waiting period?" and get a grounded answer.
- **Coverage explainer (N1, PLANNED, Wave 1):** Amit can show a merchant the mini-app screen "What am I covered for?" to explain the policy, with plain-language terms (H20).
- **Receipt and explanation (K5 BUILT; receipt H3, PLANNED, Wave 1):** Amit can show a past payout explanation to a new merchant to build confidence.

**Success metric (illustrative target, not measured):** Amit explains Chhatri to 10 new merchants in a week, and 7 of them buy within a month.

---

## 6. Anti-personas (who Chhatri is not for)

- **High-volume traders with sophisticated insurance.** A large grocery chain with a CFO and a broker will negotiate a custom business interruption policy. Chhatri is parametric and non-negotiable.
- **Risk-averse insurers who dislike parametric products.** An insurer nervous about basis risk (merchants paid when it did not rain) will not adopt. This is a known trade-off; we accept it to get same-day payouts.
- **Merchants outside Paytm's device network.** Chhatri lives inside Paytm; it needs live sales data and settlement rail access. A merchant using Square or Razorpay is not served.

---

## 7. Accessibility needs

- **Language:** Devanagari fluency required. English is optional. Marathi is PLANNED (N8, Wave 4) for Mumbai and surrounding areas.
- **Vision:** High contrast for red-green colorblind users. Zone alerts must use text or tone, not colour alone.
- **Literacy:** Messages avoid complex financial jargon, and a jargon lens explains any insurance term on tap (H20, PLANNED). Numbers are shown with rupee symbol (₹). Icons are labelled.
- **Data:** Voice (N4, PLANNED) is the preferred channel for merchants who read little, and text is always shown. Voice notes use more data than text, so replies are kept short.
- **Hearing:** Every voice message also appears as text in the chat. The Soundbox line is simulated in the prototype.

---

## 8. Assumptions to validate in pilot

1. **Merchant adoption:** Will more than 30% of merchants in the pilot zone buy Chhatri at the pilot price (the backtest gives ₹18.62 a day in Z7; the price is open)? (Hypothesis and target: yes, if trust in same-day claims is demonstrated.)
2. **Claim accuracy:** Will the area trigger's 50% threshold match merchants' lived experience of "significant loss"? (Hypothesis: yes, with a ±10% tolerance.)
3. **EDI holiday preference:** Do merchants prefer a one-day loan pause granted by their lender to a ₹600 instalment credit? (Hypothesis: yes, because it keeps their cash available for next-day restocking.)
4. **Dispute rate:** What is the dispute rate after Chhatri's explanation is shown? (Hypothesis and target: under 5%. We have no benchmark for it.)
5. **Lender confidence:** Will a lender partner accept a pre-agreed rule for EDI holiday requests? (Hypothesis: yes, because repayments already come out of Paytm settlements. No lender has agreed.)

---

## 9. Personas and the product roadmap

Horizons are the stages of the plan, not the idea ids H1 to H26. Horizon 0 is the 3 Oct final. The later horizons follow the [go-to-market plan](../05-business/go-to-market-and-pilot-plan.md).

| Persona | Horizon 0 (3 Oct final) | Horizon 1 (shadow) | Horizon 2 (live pilot) | Horizon 3 (scale) |
|---|---|---|---|---|
| **Anil** (primary merchant) | Claim monsoon (BUILT). Track, ask, grieve (PLANNED, waves 1 to 3) | Consents; triggers computed, nothing paid | Live pilot (real rain) | Same-day payouts measured; renewal |
| **Ramesh** (secondary) | Buy with waiting period (BUILT) | — | First buy before the monsoon | — |
| **Priya** (heatwave) | Story only | Story only | — | Heatwave cover, Delhi |
| **Rajesh** (officer) | Review referred claims and disputes (BUILT) | Improve SLA | Live cases | Operational scale |
| **Amit** (field) | Train on features | Support merchants | Onboarding stories | Regional expansion |

---

## Open questions

1. Is the 50% area-trigger threshold accurate to merchants' lived experience? Owner: Ujjwal Pardeshi.
2. What is the dispute rate in a real pilot, and how does it compare to health insurance (about 8% of health claims repudiated, A10)? Owner: Ujjwal Pardeshi.
3. Will a lender accept the EDI holiday as designed, or will they insist on a different alternative (e.g. paying the instalment from the payout)? Owner: Omkar Kadam.

## Changelog

- 2026-10-02 · v2.1 · aligned with the code and the demo: Anil's and Ramesh's sales (about ₹4,300 and about ₹6,000 a day), cover date, alert, Soundbox line and 17:04 and 17:05 times; Ramesh's BLOCKED story corrected (he can still buy, cover starts 25 Aug); the EDI holiday is the lender's decision; Rajesh's REFERRED versus DISPUTE work and WAIVED_BY_OFFICER; Priya's invented heatwave figures removed; planned features marked PLANNED with waves; horizons renamed to avoid clashing with idea ids; personas labelled synthetic.
- 2026-10-02 · v2 · final consistency pass against the code
- 2026-10-02 · v1 · first draft.
