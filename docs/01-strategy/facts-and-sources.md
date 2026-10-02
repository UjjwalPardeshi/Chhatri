# Facts and sources

| | |
|---|---|
| Status | Draft v1 · 2 Oct 2026 |
| Owner | Omkar Kadam |
| Audience | Judges, mentors, the team, anyone checking a number in these docs |
| Related | [Executive summary](../00-executive-summary.md) · [Competitive landscape](competitive-landscape.md) · [Regulatory and compliance](../05-business/regulatory-and-compliance.md) · [Current-state audit](current-state-audit.md) |

## TL;DR

- Every external fact in these docs carries an ID from this page (A1–A25). Every regulatory position uses the exact hedge in section B.
- Facts about our own prototype (section D) come from running it on 2 Oct 2026, and from the code paths given.
- Section E lists claims we have decided not to make, because we could not verify them or because they would overstate what the prototype shows.
- Primary regulator websites could not be reached when we checked. Where a regulatory point matters, we use reputable secondary reporting and say so.

## 1. How to use this page

- In other docs, cite a fact as "(A3)" and link this page under Related.
- A statement that is not here, and is not a code fact with a file path, is an assumption, a target or a proposal. It must be labelled as one.
- If a fact changes, update it here first, then update the docs that cite it.

## 2. A. Verified external facts

| ID | Fact | Source |
|---|---|---|
| A1 | In Q1 FY27 (Apr–Jun 2026), 1.57 crore merchants paid for Paytm payment devices. That is 27 lakh more than a year earlier. | [Paytm IR blog, Q1 FY27 results](https://paytm.com/blog/investor-relations/paytm-q1-fy27-results-revenue-grows-28-to-2448-crore-highest-ever-quarterly-ebitda-at-203-crore/) |
| A2 | Paytm's financial services revenue (lending and insurance distribution) rose from ₹561 crore in Q1 FY26 to ₹814 crore in Q1 FY27, up 45% year on year. | Same IR blog; [Free Press Journal](https://freepressjournal.in/tech/paytm-q1-fy27-results-see-bernstein-retain-outperform-rating-as-financial-services-revenue-surges-45) |
| A3 | Paytm's merchant protection plan costs under ₹2 a day, is bought in three taps in the Paytm for Business app and covers 2 lakh+ merchants. Earlier plans took 30–60 days per claim and needed multiple documents. | [Assurekit case study](https://www.assurekit.com/case-studies/paytm) |
| A4 | Paytm Insurance Broking Pvt Ltd holds an IRDAI direct (life and general) broker licence, renewed and valid to 16 Feb 2029. Paytm General Insurance withdrew its insurer-registration application (May 2024; accepted June 2024). Paytm distributes insurance. It does not underwrite. | [Business Today, Feb 2026](https://businesstoday.in/markets/stocks/story/paytm-shares-in-focus-irdai-renews-insurance-broking-license-of-subsidiary-515509-2026-02-10); [Entrackr, May 2024](https://entrackr.com/2024/05/paytm-withdraws-general-insurance-license-application-to-focus-on-distribution-biz) |
| A5 | Paytm merchant loans come from partner NBFCs and banks. They are repaid by daily deductions from settlements (EDI). Paytm provides default-loss guarantees, but the terms are not public. | Inc42 and partner announcements (partly verified; we give no DLG percentages) |
| A6 | Paytm documents an official MCP server for its Payments APIs (payment links, transactions, settlements, refunds). It needs merchant credentials. No free public sandbox is documented. | [Paytm MCP server overview](https://paytmpayments.com/docs/mcp-server-overview) |
| A7 | Bloomberg (9 Sep 2026) reported "Paytm Bets on Workplace AI Agents in Pivot Beyond Payments". Paytm told NSE the report was not a material disclosure. | [NSE filing](https://nsearchives.nseindia.com/corporate/PAYTM_09092026124019_SEIntimationMarketRumour09092026sd.pdf) |
| A8 | Clarke et al. (2012), World Bank Policy Research Working Paper 5985, studied 270 weather-index crop insurance products (one state, 13 districts, 12 crops). It found roughly a one-in-three chance of no payout even when the area-average yield was totally lost (basis risk). | [RePEc listing](https://ideas.repec.org/p/wbk/wbrwps/5985.html) |
| A9 | SEWA's heat-index insurance for women informal workers pays automatically after a heat trigger, but the money reaches members weeks later. | [CGAP](https://www.cgap.org/research/publication/confronting-climate-and-health-nexus-lessons-self-employed-womens-association); [NPR, 16 Jul 2025](https://www.npr.org/sections/goats-and-soda/2025/07/16/g-s1-76948/hot-temperatures-insurance-gig-workers-india) |
| A10 | IRDAI Annual Report 2024-25: about 3.26 crore health claims were handled, about 87% settled and about 8% repudiated. Insurers disallowed ₹15,100 crore and repudiated ₹10,937 crore of health claims in FY24. Policyholder complaints rose about 20% in FY25. | [Business Standard reporting of IRDAI data](https://www.business-standard.com/finance/personal-finance/health-insurers-reject-claims-worth-rs-15-100-crore-in-fy24-irdai-124123100615_1.html) |
| A11 | IMD warnings are colour-coded: Green (no action), Yellow (be aware), Orange (be prepared), Red (take action). | [Business Standard explainer](https://www.business-standard.com/india-news/from-red-to-orange-what-do-imd-s-colour-coded-weather-alerts-mean-123071100744_1.html) |
| A12 | PM SVANidhi has served about 75 lakh street vendors with 1 crore+ collateral-free loans. States have identified about 49.5 lakh street vendors. | [PIB](https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=1963799) |
| A13 | Mumbai extreme rain: about 250–276 mm fell in roughly 6 hours on 25–26 Sep 2024. The 2025 monsoon arrived on 26 May, the earliest in about 75 years. Colaba recorded a record 295 mm in May 2025. Santacruz recorded 244 mm on 16 Aug 2025. | [Down To Earth](https://www.downtoearth.org.in/climate-change/amid-record-breaking-monsoon-rainfall-in-mumbai-climate-scientists-explain-what-led-to-extreme-weather-event) |
| A14 | Riskwolf (Swiss, with an India subsidiary since 2024) sells parametric "claimless payouts" income cover to gig workers, farmers and SMEs. A similar idea exists, so Chhatri's novelty is the trigger (the merchant's own sales inside the payments app), the settlement-linked payout and the EDI holiday. | [Riskwolf income cover](https://www.riskwolf.com/use-cases/income-insure/) |
| A15 | BharatPe sells shop protection plans (from about ₹200 a year) covering theft, fire and natural disasters. PhonePe is an IRDAI-licensed broker that distributes health, motor, travel and life cover. | BharatPe website; PhonePe 2025 year-in-review |
| A16 | A hospital daily cash benefit pays a fixed amount for each 24 hours in hospital, whatever the bill. Typical documents are admission proof, a discharge summary showing the length of stay, ID and a claim form. Chhatri's hospital-cash claim is the income-loss counterpart of this product. | Tata AIG and ManipalCigna product pages |
| A17 | The Sarvam AI API offers speech-to-text (Saaras v3 and v4), text-to-speech (Bulbul v3), chat (sarvam-105b) and Sarvam Vision document intelligence (OCR including Hindi and English). New accounts get free starter credits; the amount is not published. | [Sarvam docs](https://docs.sarvam.ai/) |
| A18 | WhatsApp Cloud API: a Meta developer test number works without business verification. Free-form replies inside the 24-hour customer-service window are free. Outside it, an approved template is required. | [Get started](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started); [Pricing](https://developers.facebook.com/docs/whatsapp/pricing) |
| A19 | Free AI options: the Gemini API free tier (Flash models, rate-limited; free-tier content may be used to improve Google products, so we send only synthetic demo data), Tesseract OCR (Apache-2.0, with a Hindi "hin" model), Cognee (open source; works with Ollama or Gemini), n8n Community Edition (free). | [Gemini pricing](https://ai.google.dev/pricing); [Tesseract](https://github.com/tesseract-ocr/tesseract); [Cognee docs](https://docs.cognee.ai); [n8n](https://github.com/n8n-io/n8n) |
| A20 | Free hosting: GitHub Pages (static only), Vercel Hobby (static plus limited functions), Netlify free credits. The console's in-browser mock backend makes a free static deployment possible. | [Vercel pricing](https://vercel.com/pricing); [GitHub Pages](https://pages.github.com) |
| A21 | MochaTrade, a hackathon partner, is a YC (Spring 2026) fintech for leveraged perpetual futures on US stocks. | [YC company page](https://ycombinator.com/companies/mochatrade) |
| A22 | The DPDP Rules, 2025 were notified on 13 Nov 2025 (published 14 Nov). The rollout is phased: 14 Nov 2025; 14 Nov 2026 (for example, consent managers); 14 May 2027 for the substantive obligations (consent, notices, breach reporting within 72 hours and more). | [Hogan Lovells](https://www.hoganlovells.com/en/publications/indias-digital-personal-data-protection-act-2023-brought-into-force-); [AMS Shardul](https://www.amsshardul.com/insight/enforcement-of-the-dpdp-act-and-notification-of-the-dpdp-rules/) |
| A23 | RBI's FREE-AI committee report (Framework for Responsible and Ethical Enablement of Artificial Intelligence) was released on 13 Aug 2025. It sets out 7 sutras (Trust, People First, Innovation, Fairness, Accountability, Explainability, Resilience) and 26 recommendations under 6 pillars. It is advisory until RBI issues directions. | [RBI press release](https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=61018); [KPMG summary](https://kpmg.com/in/en/insights/2025/09/rbis-free-ai-committee-report-in-the-financial-sector.html) |
| A24 | IRDAI's Master Circular on Health Insurance Business (29 May 2024) requires insurers to decide cashless requests within 1 hour and final discharge authorisation within 3 hours (effective 1 Aug 2024). | [Outlook Retirement](https://retirement.outlookindia.com/plan/news/cashless-health-insurance-claim-settlements-from-august-1-all-you-need-to-know) |
| A25 | The RBI (Digital Lending) Directions, 2025 were issued on 8 May 2025. They consolidate and replace the Sep 2022 digital lending guidelines and the June 2023 DLG guidelines. | [RBI press release](https://rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=60403) |

## 3. B. Regulatory positions (stated with these hedges only)

All of these positions are to be confirmed with the partner insurer's compliance team and counsel.

- **Insurance Act 1938, s.64VB (cash before cover).** An insurer may not assume risk until the premium is received, or guaranteed or deposited in the prescribed manner. Chhatri's design: cover for a day starts only when that day's premium has been received. That is either the first 30-day prepayment or the previous evening's settlement deduction, made with the merchant's explicit standing consent. The 30 days is our product design, not a rule in s.64VB.
- **Grievance ladder.** First the insurer's grievance redressal officer. Then IRDAI's Bima Bharosa portal, which says complaints are attended within 14 days. Then the Insurance Ombudsman (Insurance Ombudsman Rules, 2017; free to the policyholder).
- **Parametric (index) insurance** already exists in India, for example weather-index crop insurance under RWBCIS. A new merchant-income parametric product would need product filing by a general insurer, possibly through IRDAI's regulatory sandbox route.
- **Lending.** Under the RBI (Digital Lending) Directions, 2025 (A25), any instalment deferral is the lender's decision under its board-approved policy. Chhatri can only request an EDI holiday, or have the insurer pay the instalment as part of the payout. Whether a pre-agreed holiday counts as a restructuring is for the lender's compliance team to decide.
- **Data protection.** Design now for purpose-specific, withdrawable consent (A22). Health data on hospital slips needs the strictest handling: minimise it, mask it and delete it on request.

## 4. D. Facts about our prototype (measured on 2 Oct 2026, commit 86575ea)

| Fact | Where it comes from |
|---|---|
| Backend: 1,711 fast and 36 slow tests pass, with 99.7% coverage. | `make test-backend`, `make test-slow` ([Makefile](../../Makefile)) |
| `make demo-check` passes 70 of 70 checks. | [backend/scripts/demo_check.py](../../backend/scripts/demo_check.py) |
| Frontend: 262 of 264 unit tests pass. Two fail: the Cases panel and the Overview live map. Fix X1 is planned. | `make test-frontend` (Vitest) |
| Infra: 118 of 118 tests pass. | `make test-infra` |
| Without API keys, every integration is SIMULATED and labelled. Intent detection is a word-list classifier, and the LLM is only a fallback for unknown text. Speech-to-text uses canned demo transcripts. The slip-reading simulator reads data embedded in the sample slip images. | [integrations/registry.py](../../backend/chhatri/integrations/registry.py), [conversation/intents.py](../../backend/chhatri/conversation/intents.py) |
| The only trained model is a LightGBM quantile model of expected sales (p10/p50/p90). It was trained on simulated sales driven by real Open-Meteo rainfall (Colaba and Santacruz, 2024–2025). | [backend/chhatri/forecast/](../../backend/chhatri/forecast/) |
| The demo calibration is circular by design. Simulation parameters are searched so the replay reproduces the demo numbers (Z7 37%, ₹4,380, ₹58,900). Premiums are priced as expected loss ÷ (1 − 0.35), so every zone's backtest loss ratio is about 65% by construction. | [pipeline/targets.py](../../backend/chhatri/pipeline/targets.py), [day_search.py](../../backend/chhatri/pipeline/day_search.py), [level_search.py](../../backend/chhatri/pipeline/level_search.py) |
| The backtest uses simulated sales with real rainfall, over Jun–Sep of 2024 and 2025. Chhatri paid 89 of 148 "real drops" (60%) against 49 (33%) for a weather-only trigger. 36 of Chhatri's 125 payouts (29%) lacked a real drop, against 287 of 336 (85%) for weather-only. The simulator defines a "real drop" as a loss of at least 40% of expected sales. | [backend/chhatri/backtest/](../../backend/chhatri/backtest/) |
| The round-1 deck showed Z7 at 41%. The prototype shows 37%, which produces the 63% drop and the ₹1,380 payout. | [docs/DEMO.md](../DEMO.md) |
| Policy rules, version pilot-0.1:<br>• payout share 50%<br>• area trigger: the hourly index is below 50% for 3 consecutive hours and below the model's conformal lower bound, during an alert, with at least 20 shops in the index<br>• area cap ₹2,500 per shop per day<br>• hospital-cash cap ₹1,500 per day, up to 3 automatic days<br>• name match ≥ 85 (token-set ratio)<br>• slip confidence ≥ 0.80<br>• 7-day waiting period with a 72-hour alert look-ahead<br>• annual limit ₹30,000<br>• dispute SLA 24 hours<br>• premium loading 0.35, minimum ₹2 a day; the first payment prepays 30 days | [backend/chhatri/policy/rules.yaml](../../backend/chhatri/policy/rules.yaml) |
| The prototype (76 commits) was built between 29 Sep and 1 Oct 2026, before the on-site day. The organisers confirmed pre-built work is allowed. | [Repository history](https://github.com/UjjwalPardeshi/Chhatri/commits/main) |

## 5. E. Claims we do not make

- That the backtest proves performance on real merchants. It runs on simulated sales driven by real rainfall.
- That Paytm has an area income index product. Our "Area Income Signal" is our own roadmap idea.
- A precise day range for SEWA payouts. We say "weeks".
- Any amount for Sarvam's free credits, or any Gemini model version number.
- Any published judging criteria or weights for this hackathon. None are published.
- That an EDI holiday is, or is not, a restructuring. That is the lender's call.
- That the 8-hour on-site build window is official. It is reported, not published.
- That any insurer or lender has agreed to partner with us. A pilot partner will be approached after the hackathon.

## Open questions

1. Can a partner insurer's compliance team confirm the s.64VB design in section B? Owner: Omkar Kadam.
2. Which lender partner would confirm how a pre-agreed EDI holiday is treated? Owner: Omkar Kadam.
3. Refresh section D after fixes X1–X8 land, for example to 264 of 264 frontend tests. Owner: Ujjwal Pardeshi.

## Changelog

- 2026-10-02 · v1 · first draft, from the team's fact-check of 1–2 Oct 2026.
