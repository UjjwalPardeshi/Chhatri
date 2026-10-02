# Competitive landscape

| | |
|---|---|
| Status | Draft v1.6 · 3 Oct 2026 · the rival scan is of 2 Oct; the status of Chhatri's own features is of 3 Oct |
| Owner | Omkar Kadam |
| Audience | Judges, mentors, the team, rivals; the public may read it, so be factual and generous |
| Related | [Rival teardown appendix](rival-teardown-appendix.md) · [Facts and sources](facts-and-sources.md) · [Current-state audit](current-state-audit.md) · [Vision and positioning](../02-product/vision-and-positioning.md) · [PRD §3](../02-product/prd.md) · [Requirements traceability matrix](requirements-traceability-matrix.md) |

## TL;DR

- Among the products we compared (section 1), none pays lost income from the shop's own sales within hours. Paytm's merchant protection plan shows that merchants will buy cover (A3), and earlier plans took 30–60 days per claim. In our replay, Chhatri pays 4 simulated minutes after the trigger, from simulated sales.
- Parametric (index-linked) cover exists (Riskwolf, SEWA, weather-index crop insurance). The sources show basis risk, meaning no payout in a real loss (A8), and, for SEWA, money that arrives weeks after the event (A9).
- On 2 Oct 2026 we read 28 public repositories from the Paytm Build for India hackathons ([appendix](rival-teardown-appendix.md)). Two state Mumbai Track 2, three are from the Delhi edition, and 11 had a demo link that answered at least once. Among them we did not find one that starts a claim and pays it from the merchant's own sales. Most are guidance, readiness or claim-filing assistants.
- Their strengths: step-by-step journeys, evidence and explanation traces, honest-wording tests, voice-first interfaces, published evaluations and zero-login demos. Praman's repository was updated on 2 Oct, after our first pass, and is the closest overlap in the claims stages.
- We adopted 26 ideas, H1 to H26, and credit each project by name. H1 to H12 came from the first scan. H13 to H26 (section 4.2) came from the 2 Oct teardown.
- Where others are ahead today: a public demo link, and live AI that has actually been run. We have built the merchant mini-app (N1), Ask Chhatri, the slip pre-check and voice (N2 to N4) behind flags, but no AI key has been tried, and the static build (N7) is not deployed. An unfinished feature is hidden, never shown half-working.

## 1. What merchants have today

| Product or scheme | Who pays | How it works | Time to money | Notable |
|---|---|---|---|---|
| **Paytm merchant protection plan (existing)** (A3) | Merchant (premium) | Bought in three taps in the Paytm for Business app, under ₹2 a day; 2 lakh+ merchants covered. | Not published; earlier plans took 30–60 days with multiple documents | Shows merchants will buy low-priced cover. |
| **Weather-index crop insurance** (A8) | Insurer | Pays on a weather index, not on assessed loss. No document. | Not stated | Roughly a one-in-three chance of no payout even when the area-average yield was totally lost (basis risk). |
| **SEWA heat-index cover** (A9) | SEWA via insurer | Women informal workers: automatic payout after a heat trigger. No documents. | Weeks after the event | Automatic, but the money arrives well after the loss. |
| **Riskwolf parametric income cover** (A14) | Riskwolf | Gig workers, farmers, SMEs: automatic payout on an index. No form. | Not stated | Claimless is the idea; the trigger is not the merchant's own data. |
| **Hospital daily-cash benefit** (A16) | Insurer | Fixed payment per 24 h in hospital. Needs admission proof, a discharge summary, ID and a claim form. | Not stated; documents come first | Chhatri's hospital-cash claim is the income counterpart. |
| **PM SVANidhi (street vendors)** (A12) | Government + lenders | Collateral-free loans to vendors. No direct cover. | Not applicable (a loan) | 1 crore+ loans to about 75 lakh vendors; no embedded insurance. |
| **Shop insurance (BharatPe, PhonePe)** (A15) | Various insurers | BharatPe: theft, fire and natural disasters, from about ₹200 a year. PhonePe brokers health, motor, travel and life cover. | Not stated | Asset cover; no income claims. |

**The gap:** merchants lose sales during a shock (monsoon, illness) and need money within hours, not weeks. Among the products above, we did not find one that pays lost income from the shop's own sales on the same day.

## 2. Hackathon projects (read on 2 Oct 2026)

One row per project, with every column, is in the [rival teardown appendix](rival-teardown-appendix.md). The tables here keep the links and the overlap with Chhatri. Test counts are as each project states them, and we ran none of them. Demo status is from two HTTP checks on 2 Oct. **Both OK** means the link answered both times. **Mixed** means it answered once and timed out once, so re-check it before you quote it. **None found** means the repository lists no address. Projects are grouped by what their own README says about the edition and the track.

### 2.1 Mumbai edition, Track 2 (stated in the README)

| Project | Team | Repo | Demo, 2 Oct | Tests (as stated) | Strengths | Overlap with Chhatri |
|---|---|---|---|---|---|---|
| **Praman** | HackOverFlow | [github.com/rithvikshettyy/praman-paytm](https://github.com/rithvikshettyy/praman-paytm) | None found | 930 (README on 2 Oct; 703 earlier the same day) | Health-claim readiness; a rule engine with no model or clock; a verified-by field on every rule; respondent router with response clocks; a checklist where photos tick slots; Marathi voice; consent and delete | Closest overlap in the understand, submit and resolve stages, and the same principle: rules decide. Praman advises and drafts, and its README says nothing is filed or sent. We took H4, H8, H10, H12, H13, H15, H17 and H22. |
| **Paytm Virasat** | Not stated | [github.com/JACELL100/paytm-virasat](https://github.com/JACELL100/paytm-virasat) | None found | Not stated (about 80 test functions found) | Claims co-pilot after a death in the family; proof-of-life flow; claim-pack PDFs | A different journey (after a death). No idea adopted. |

**Update on 2 Oct.** Praman's repository was updated on 2 Oct, after our first pass. Its README test count went from 703 to 930 during the day, so treat any number about it as a snapshot.

### 2.2 Track 2 stated, edition not stated

| Project | Repo | Demo, 2 Oct | Tests (as stated) | Strengths | What we took, or overlap |
|---|---|---|---|---|---|
| **FinSaathi** (this repo is not confirmed as the finalist team's) | [github.com/Bhumik16/FinSaathi](https://github.com/Bhumik16/FinSaathi) | None found | None found | README: "Paytm Buildathon 2026, Track: AI-Powered Financial Journeys"; created 24 Sep 2026. A front-end prototype of a multi-agent "journey agent", with an agent activity drawer and a decision panel | None adopted. The name matches a finalist team on the organisers' poster, but the repo owner is not the team lead named there and another public repo has the same name (2.5), so we do not say this repo is the finalist's. |
| **Sahaj** (The NPM Tigers) | [github.com/shiv9956/Sahaj](https://github.com/shiv9956/Sahaj) | [Live](https://sahaj-web-pi.vercel.app), both OK | 54 (phase reports; 39 in an earlier one) | Trust receipts (sources and assumptions visible); Hinglish voice with amount confirmation chips; tappable jargon; next-best-action bar; "forget everything"; judge mode; a published evaluation (self-reported) | H2, H3, H7, H18, H20, H21, H23, H25 |
| **SetuAI** | [github.com/ronakparmar11/setuai](https://github.com/ronakparmar11/setuai) | [Live](https://setuai-two.vercel.app), mixed | None found | Front-end design for four journeys; a confidence label and proof lines under answers | None adopted. Its copilot, scan and voice screens show fixed responses. |
| **SAHAAY** | [github.com/vishesh1916/sahaay---AI-recovery-agent-](https://github.com/vishesh1916/sahaay---AI-recovery-agent-) | [Live](https://sahaay-six.vercel.app), both OK | None stated (4 test files) | Evidence badges with seven states; context carried across steps; a deterministic gap engine | H1, H2 |
| **FINPATH** (not FinPath AI) | [github.com/Rushilp21/Paytm-Hackathon---GDuo](https://github.com/Rushilp21/Paytm-Hackathon---GDuo) | None found | 25 Flutter tests and 8 backend smoke checks (README) | Affordability engine; a review dialog before extracted data is used; consent toggles with an activity log; scam-message patterns; five language options with speech | H5, H15, H19, H23 |
| **Claim Advocate** | [github.com/arpit2705/Claim_Advocate](https://github.com/arpit2705/Claim_Advocate) | [Link](https://claim-advocate-pi.vercel.app), mixed | None stated (14 test files) | Policy-grounded claim review; an evidence trace in every response; a sanitiser against prompt injection; exact plus semantic retrieval | H2, H5, H14, H16 |
| **Sahayak** | [github.com/ayushraj5634/Sahayak_Paytm](https://github.com/ayushraj5634/Sahayak_Paytm) | [Live](https://sahayak-sigma-lyart.vercel.app), both OK | None found | Loan-rejection coach with a debt-to-income what-if slider; bilingual | None adopted. Loans only. |
| **COVE2E** | [github.com/sohanpal17/COVE2E](https://github.com/sohanpal17/COVE2E) | None found | 25 (README) | Stuck-claim recovery plan; a deterministic action gate; an outcome verifier | H10 |
| **AeroFin AI** | [github.com/BhaskarShah05/paytm-aerofin-ai](https://github.com/BhaskarShah05/paytm-aerofin-ai) | The listed address returned 404 in both checks | None found | Jargon buster with an out-of-pocket calculator; human decision gates | H20 |
| **Clarity** | [github.com/anmoltyagi18/clarity](https://github.com/anmoltyagi18/clarity) | None found | None found | Debt-exposure checker with verdict badges and plain explanations | None adopted. Lending only. |

### 2.3 Delhi edition (19 Sep 2026)

| Project | Repo | Demo, 2 Oct | Tests (as stated) | Strengths | What we took, or overlap |
|---|---|---|---|---|---|
| **Nirdesh** (Delhi, Track 2) | [github.com/himangshukumbhakar58-cpu/paytm-nirdesh](https://github.com/himangshukumbhakar58-cpu/paytm-nirdesh) | [README link](https://paytmnirdesh.vercel.app) answered in our first check. The repo homepage link returned 404 | None found | Step-by-step journey with a progress bar; three-column layout; English and Bengali | H1: journey steps with "you are here" (our N1 tracker). H11: bilingual text. |
| **One-Tap Credit** (Team1; Delhi, Track 2) | [github.com/carbonFibreCode/paytm-one-tap-credit](https://github.com/carbonFibreCode/paytm-one-tap-credit) | [Link](https://paytm-one-tap-credit.vercel.app), mixed | 32 (README) | 14 ordered hard gates as pure functions; affordability first; an explanation and counterfactual for every decision; a frequency cap on offers | H9: no loan offers during distress (X8). H10: the same pure-engine principle as K4. H14: counterfactuals. H17: numbers only from engine facts. |
| **Resolve OS** (track: "Autonomous AI Teammates") | [github.com/sparsh101sparsh/resolve-os](https://github.com/sparsh101sparsh/resolve-os) | [Live](https://paytm-desk.vercel.app), both OK | 39 tests, 19 of 19 rubric checks and 40 policy benchmarks (README) | A deterministic policy engine where the model has no authority over funds; SHA-256 policy tokens; an immutable audit schema; a fixture fallback; judges can change the data and watch the policy react | H7 (fallback switch), H8 (counts), H10 (shared principle), H24 (what-if), H25 (published evaluation) |

### 2.4 Mumbai edition, another track

| Project | Repo | Demo, 2 Oct | Tests (as stated) | Strengths | What we took, or overlap |
|---|---|---|---|---|---|
| **Soundbox Saathi** (Merchant Growth AI) | [github.com/ShivprasadChinnchole/soundbox-saathi](https://github.com/ShivprasadChinnchole/soundbox-saathi) | None found | No Python tests; 22 lines of Flutter widget tests | Voice-first merchant insights; numbers come only from tools; a propose, confirm, execute lifecycle; an offline fallback brain | H11 (bilingual text), H17 (numbers only from tools), H26 (mode label) |

This project is from another track. Its patterns (tool-owned numbers, voice, an offline fallback) are why it is here.

### 2.5 Edition or track not stated in the repository

| Project | Repo | Demo, 2 Oct | Tests (as stated) | Strengths | What we took, or overlap |
|---|---|---|---|---|---|
| **FinPath AI** (not FINPATH) | [github.com/Sushrut-Kale/paytm](https://github.com/Sushrut-Kale/paytm) | [Live](https://finpath-ai-three.vercel.app), both OK | 18 (README) | Goal-first journeys; a deterministic readiness engine; a **zero-login demo route** | H5, H6, H15, H24 |
| **FinSaathi** (health claims; another repo with this name is in 2.2) | [github.com/agniv-dutta/FinSaathi](https://github.com/agniv-dutta/FinSaathi) | [Live](https://finsaathi-five.vercel.app), both OK | None found | Health-claims assistant: policy breakdown, document checklist, claim tracker. Overlap in scope, not in trigger or payout model | H1 |
| **Vanifi** | [github.com/dare-devil-coder/Vanifi](https://github.com/dare-devil-coder/Vanifi) | None found | 15 test assertions (README) | Loan offers suppressed in the decision layer when the user is stressed; a safe-to-spend signal | H9 |
| **Rakshak** | [github.com/Akataruka/paytm-hackathon](https://github.com/Akataruka/paytm-hackathon) | [Live](https://paytm-hackathon-lake.vercel.app), both OK | None found | Every external call returns data, a mode and a fallback reason; rules decide, the model explains. Probably another track | H26 |
| **AI-CLARITY-LAYER** | [github.com/Sahajananda-ai/AI-CLARITY-LAYER](https://github.com/Sahajananda-ai/AI-CLARITY-LAYER) | None found | None found (the README says checks were manual) | A browser-only explainability layer; seven named document checks; an on-device PDF statement | H3 |
| **JeevanFlow** (added after the first pass) | [github.com/Medhavi1906/JeevanFlow](https://github.com/Medhavi1906/JeevanFlow) | None found | None found (one placeholder) | Life-event decision support (wedding, education, house, medical, job loss): health score, funding gap, runway, what-if. A small intent classifier, no language model | None adopted. No overlap with income cover. |
| **ClaimSaathi** (added after the first pass) | [github.com/buildwithshikhar/paytmbuildforbharat](https://github.com/buildwithshikhar/paytmbuildforbharat) | None found (a free-tier Render config exists, no address) | One test file, about 11 tests; no README | Coverage Q&A on one preloaded health policy. Waiting periods are computed in code, and every answer cites page and clause | None adopted (found on 2 Oct). It shares the principles behind H10 and H17. |
| **GrowSAATHI** (added after the first pass) | [github.com/ShivamNishad999/paytm-financial-intelligence-platform](https://github.com/ShivamNishad999/paytm-financial-intelligence-platform) | None found | None found | Flutter app for merchant growth: insights, an action centre, campaigns and chat, with rule-based replies and a demo and live toggle | None adopted. Its demo and live toggle is the same idea as our X6 labels, which were already planned. |

### 2.6 Created on the Bengaluru edition date (21 Mar 2026)

The Bengaluru tracks were "AI for Paytm Users" and "AI for Small Businesses", not "AI-Powered Financial Journeys". Four repositories were created on 21 Mar 2026, and their READMEs do not state the edition: [Vyapaar Saathi](https://github.com/NikhilSetty/PaytmHackathon) (voice inventory), [SahayAI](https://github.com/drraghavendra/paytm-hackathon) (WhatsApp voice assistant for sellers), [Smart Receivables Recovery](https://github.com/EswarDivi/PaytmHackathon) and [SMB virtual COO](https://github.com/axvrma/paytm-hackathon). We adopted nothing from them.

## 3. Capability matrix: how we compare

**Legend.** Yes = found in the repository or README. Partial = partial, gated by an API key, or simulated. No = not found in our read of the repository (we may have missed it). n/a = the project is about something else.

| Capability | Chhatri with the flags off | Chhatri with the flags on (BUILT) | Praman | One-Tap Credit | Nirdesh | Sahaj | Claim Advocate | FinPath AI | SAHAAY |
|---|---|---|---|---|---|---|---|---|---|
| Claim starts and pays itself from the merchant's own sales (area claim, no form) | Yes (K1, simulated sales) | Yes | No | n/a | No | No | No | No | No |
| Hospital-cash claim with one photo and no claim form | Yes (K2: check-in, one photo, engine decision) | Yes, with a pre-check (N3, `n3_slip_precheck`) | No (readiness checklist; nothing is filed) | n/a | No | No | No | No | No |
| Payout tied to a loan instalment | Partial (K3: a simulated pause, no lender decision) | Yes (X4, `x4_lender_request`: a request the simulated lender decides) | No | No | No | No | No | No | No |
| Walks the health-claims example end to end (understand, submit, track, resolve) | Partial (the claim runs in the console and phone simulator; no merchant app, pre-check or free Q&A) | Yes (N1, N2, N3, N5 behind their flags; the AI parts untried with a key) | Partial (readiness, checklist, routing, drafts) | n/a | Partial (scripted) | No | Partial (review and appeal) | No | Partial |
| Rules decide the money, the model does not | Yes (K4) | Yes | Yes | Yes | No | Yes | Partial (the model reasons, rules validate) | Yes | Yes |
| Tamper-evident audit log (hash chain) | Yes (K7) | Yes | No (an events table) | Partial (an audit trail, no hash chain found) | No | No | No | Partial (an `audit_logs` table, no hash chain found) | No |
| Live AI in the demo, not only word lists | Partial (Sarvam when keyed; word-list intents) | Partial (Gemini, then Sarvam, with labels; tested against fakes only, no key run) | Partial (Sarvam, with a key) | Partial (Sarvam copy only) | No | Partial (Sarvam, Cognee) | Partial (Groq) | Partial (Gemini, with a fallback) | Partial (Groq) |
| Indic voice | Partial (Hindi through Sarvam, with a key) | Partial (N4 Hindi voice, `n4_voice`, untried with a key; N8 Marathi text, a draft) | Yes (Marathi) | No (text in four languages) | No (text in Bengali) | Yes (Hinglish) | No | No | Partial (Hindi voice input) |
| Public demo link | No | Static build BUILT (N7); not deployed, no address yet | No | Mixed | README link; homepage link 404 | Yes | Mixed | Yes | Yes |
| Test count stated | Measured by us (below) | Re-measured in the final run | 930 (README) | 32 (README) | None found | 54 (phase reports) | None stated (14 test files) | 18 (README) | None stated (4 test files) |

**Key observations.**
- We did not find an automatic area claim from the merchant's own sales in the other repositories we read.
- Rivals lead on public demo links and merchant-facing screens, and Sahaj and Praman on voice. FINPATH offers five language options. We have built N1, N4, N7 and N8, and they still need rehearsal, a key, a deployment and a native review.
- Chhatri's own counts at the 2 Oct baseline (commit 86575ea): backend 1,711 fast and 36 slow tests at 99.7% coverage, frontend 264 tests, infra 118, and 70 of 70 demo checks. Since then the backend has grown to 3,284 collected tests (63 slow). Praman's README states 930. The counts are not comparable: different languages and test styles.

## 4. Feature harvest: what we learned and adopted

We adopted 26 ideas and credit the source projects by name. Every idea is P0 (team decision, 2 Oct 2026). All of them are now built, each behind a feature flag where it is a screen or a route ([build plan](../06-delivery/build-plan.md)). "Built" means the code and its tests exist: the AI paths have not been run with a key.

### 4.1 H1 to H12 (first scan)

| ID | Idea | Credit | What Chhatri does | Status |
|---|---|---|---|---|
| H1 | Step-by-step journey with "you are here" | Nirdesh; SAHAAY; FinSaathi (agniv-dutta) | N1 claim tracker: Detected → Checked → Decided → Paid → EDI holiday. Each step shows state, reason and next step, including the REFERRED and DISPUTE paths | BUILT · `n1_miniapp` |
| H2 | Evidence trace: why this amount, with source badges | Claim Advocate; SAHAAY; Sahaj | The K5 card already shows the formula and numbers (BUILT). N1 adds source badges and the receipt link | BUILT (K5 card; N1 view behind `n1_miniapp`) |
| H3 | Payout receipt | Sahaj (trust receipt); AI-CLARITY-LAYER (PDF statement) | N1 receipt: decision id, rules version, formula, sources, audit hash prefix, grievance path. Printable | BUILT |
| H4 | Honest-wording test | Praman | X7: fails on promise words, money that is not in the decision facts, or "paid" before a payout record exists | BUILT |
| H5 | The merchant confirms what was read; a readiness checklist with no score | Claim Advocate; FinPath AI; FINPATH | N3: shows what was read, and the merchant confirms before the checks run. A three-line checklist, no number | BUILT · `n3_slip_precheck` |
| H6 | Zero-login public demo | FinPath AI | N7: a static build of the console in mock mode with a permanent SIMULATED banner. The repo owner deploys it. No address exists yet | Static build BUILT; not deployed |
| H7 | Glass-box provider panel with a fallback switch | Sahaj; Resolve OS | X6: LIVE, SIMULATED or FALLBACK for each component, plus a switch that forces fallback | BUILT · `x6_provider_panel` |
| H8 | Real operational counts | Praman; Resolve OS | K8 ops strip: counts from the database only, never projected | BUILT · `h8_ops_strip` |
| H9 | No loan offers during distress; frequency cap | Vanifi; One-Tap Credit | X8: no loan, top-up or cross-sell message while an alert covers the zone or a claim or dispute is open. A message cap, and a test enforces it | BUILT · `x8_distress_guard` |
| H10 | Deterministic core; the model has no authority over money | Resolve OS; One-Tap Credit; Praman; COVE2E | K4 policy engine, thresholds in `rules.yaml`. The same principle as these projects. K4 was already built | BUILT |
| H11 | Bilingual templates, not model translation | Nirdesh; Soundbox Saathi | The message catalogue, Hindi and English, filled from decision facts. Marathi (N8) uses the same catalogue | Hindi and English BUILT; Marathi a draft behind `n8_marathi` |
| H12 | Visible, measured test counts | Praman | README and pitch show measured counts and never round up | Not done: the README does not state its counts; measured counts are written after the final run |

### 4.2 H13 to H26 (2 Oct teardown)

All fourteen are BUILT (the AI ones untried with a key). Repository links are in section 2 and in the [appendix](rival-teardown-appendix.md).

| ID | Idea | Where it lands | Status | Credit |
|---|---|---|---|---|
| H13 | **Verified-by badges.** Every rule, number and clause shown to a merchant or officer carries its source (rules version and clause, sales index, alert id, KYC, slip) and time | K5, N1 receipt, N2, console | BUILT | [Praman](https://github.com/rithvikshettyy/praman-paytm) |
| H14 | **Counterfactual in every explanation.** What would have changed the outcome, produced by the engine re-running its own rule and not by a model. Example (proposed wording): "Z9 fell to 61% with no alert; with an alert and 3 hours below 50% it would have paid" | K4, K5, N1 receipt, console | BUILT | [One-Tap Credit](https://github.com/carbonFibreCode/paytm-one-tap-credit); [Claim Advocate](https://github.com/arpit2705/Claim_Advocate) (evidence chain) |
| H15 | **Slip pre-check.** Document-type check, slot checklist and a confidence gate ("ask, don't assume": below the threshold, confirm or retake). The merchant confirms the extracted fields before checks run | N3 | BUILT · `n3_slip_precheck` | [Praman](https://github.com/rithvikshettyy/praman-paytm); [FinPath AI](https://github.com/Sushrut-Kale/paytm); [FINPATH](https://github.com/Rushilp21/Paytm-Hackathon---GDuo) |
| H16 | **Prompt-injection defence** for slips and chat. Untrusted text is wrapped and never obeyed. Red-team tests | N2, N3, X7 | BUILT | [Claim Advocate](https://github.com/arpit2705/Claim_Advocate) |
| H17 | **Ask Chhatri cites policy clauses** (C1 to C12 chips). Every number comes from engine facts. A guard blocks unsupported numbers and promises | N2 | BUILT · `n2_ask_chhatri` | [Praman](https://github.com/rithvikshettyy/praman-paytm); [One-Tap Credit](https://github.com/carbonFibreCode/paytm-one-tap-credit); [Soundbox Saathi](https://github.com/ShivprasadChinnchole/soundbox-saathi) |
| H18 | **Voice confirmation chips** for amounts and dates (proposed wording: "₹1,500 — सही है?") | N4 | BUILT · `n4_voice` | [Sahaj](https://github.com/shiv9956/Sahaj) |
| H19 | **Scam-message warning** in chat: OTP requests, advance fees, "guaranteed claim", urgency, short links | N2 | BUILT · `n2_ask_chhatri` | [FINPATH](https://github.com/Rushilp21/Paytm-Hackathon---GDuo) |
| H20 | **Jargon lens.** Tap any insurance term for a plain Hindi or English explanation with an example | N1 coverage explainer | BUILT · `n1_miniapp` | [Sahaj](https://github.com/shiv9956/Sahaj); [AeroFin AI](https://github.com/BhaskarShah05/paytm-aerofin-ai) |
| H21 | **Next-best-action bar.** Every screen and every chat reply ends with a clear next step, with no dead ends | N1, N2 | BUILT · `n1_miniapp`, chat replies `n2_ask_chhatri` | [Sahaj](https://github.com/shiv9956/Sahaj) |
| H22 | **Grievance ladder with response clocks** and a respondent router (who owns this complaint: Paytm, the insurer or the lender) | N5 | BUILT · `n5_grievances` | [Praman](https://github.com/rithvikshettyy/praman-paytm) |
| H23 | **Consent activity log** (what was used, for what, when) and "forget my slip" erase | N6 | BUILT · `n6_consents` | [Sahaj](https://github.com/shiv9956/Sahaj); [FINPATH](https://github.com/Rushilp21/Paytm-Hackathon---GDuo) |
| H24 | **What-if panel for judges.** Change the rain or sales inputs and watch the deterministic engine recompute. Read-only, no writes | K8 console, N7 | BUILT · `h24_whatif` | [Resolve OS](https://github.com/sparsh101sparsh/resolve-os); [FinPath AI](https://github.com/Sushrut-Kale/paytm) |
| H25 | **Published AI evaluation.** Intent accuracy on a labelled set, the guard's red-team block rate, and slip-field accuracy on synthetic labelled slips. Numbers appear only once measured | N2, N3, console `/evals` | Offline harness BUILT · `h25_evals`; no run stored | [Sahaj](https://github.com/shiv9956/Sahaj); [Resolve OS](https://github.com/sparsh101sparsh/resolve-os) |
| H26 | **Every AI reply carries its mode** (LIVE, SIMULATED or FALLBACK), provider and fallback reason | N2, N3, N4, X6 | BUILT | [Rakshak](https://github.com/Akataruka/paytm-hackathon); [Soundbox Saathi](https://github.com/ShivprasadChinnchole/soundbox-saathi) |

Specs: H13 and H14 in [fs-09](../02-product/feature-specs/fs-09-policy-engine-and-audit.md); H15 in [fs-02](../02-product/feature-specs/fs-02-hospital-cash-claim.md); H16 to H19 and H26 in [fs-05](../02-product/feature-specs/fs-05-ask-chhatri.md); H20 and H21 in [fs-04](../02-product/feature-specs/fs-04-merchant-mini-app.md); H22 in [fs-06](../02-product/feature-specs/fs-06-explanations-disputes-and-grievance.md); H23 in [fs-07](../02-product/feature-specs/fs-07-cover-purchase-and-consent.md); H24 and the console side of H26 in [fs-08](../02-product/feature-specs/fs-08-claims-officer-console.md); H25 in the [AI evaluation plan](../04-engineering/ai-evaluation-plan.md).

### 4.3 Ideas we looked at and did not adopt

| Idea | Why not | What we do instead |
|---|---|---|
| A numeric 0 to 100 readiness score for the slip | False precision, and it invites trial and error | N3: a checklist with PASS and WARN lines and no score |
| Multi-agent orchestration; vector search over policy text | Our policy wording is 12 clauses, and a model that calls the engine as a tool breaks ADR 0001 | Clause chips C1 to C12, with every number from engine facts (H17) |
| Blockchain registry or on-chain claim ledger | Out of scope for income cover | The hash-chained audit log (K7) |
| XP, streaks, progress rings, payout "tiers" | A claim is not a game, and our payout is one formula with a cap | A plain tracker (H1) and one formula shown with its numbers (H2) |
| A model that decides money or picks the next money action | Code decides money (ADR 0001) | The deterministic policy engine |
| Frosted-glass visual style | Not part of our design system | Plain CSS tokens in the console. The mini-app follows the same tokens |
| Paid AI services | Free tools only | Gemini free tier, Sarvam credits, then templates |
| A UI framework for the whole product | The console is built and tested on plain CSS tokens | The console keeps plain CSS. Only the mini-app uses Tailwind CSS v4 and shadcn/ui, scoped under `.miniapp`. No charting library |

## 5. Where Chhatri is different

**The trigger (BUILT, on simulated sales and simulated alerts).** Chhatri measures the loss in the merchant's own sales, not an area rain gauge or a crop-yield model, and pays the same merchant. Among the products in section 1 and the repositories we read, we did not find another that does. The mechanism:

- Every shop has an expected day, from its own history.
- A weather alert covers the zone for the whole window (IMD-style, simulated in the prototype).
- At the zone's third consecutive hour below 50% of expected sales, below the model's conformal lower bound, with at least 20 shops in the index, the trigger fires.
- Each insured shop in the zone is paid ½ × its own expected day × the drop %, capped at ₹2,500 a day.
- One shop's slow day does not pay: the area index needs at least 20 shops and a drop that holds for 3 hours.

Riskwolf uses an external index (A14). SEWA and crop insurance use rainfall, heat or yield (A8, A9).

**Settlement-linked payout (BUILT, simulated rail).** The money is credited with the evening settlement, 4 simulated minutes after the decision, so the merchant can use it for the day or the instalment, instead of waiting weeks (compare SEWA, A9).

**EDI holiday (K3 BUILT as a simulated pause; X4 BUILT behind `x4_lender_request`).** After an approved payout, Chhatri requests the lender's pre-agreed EDI holiday. The lender decides under its own policy: loan active, not in arrears, holiday allowance left. With the flag off the prototype pauses the instalment directly through the simulated lender, with no guard and no grant or refuse step. With it on, X4 sends a request, applies the guard (loan active, not in arrears, holiday allowance left), lets the simulated lender grant or refuse, and the wording says the lender decides.

**Same-day explanations in Hindi (BUILT).** The "why did I get this much?" answer is a Hindi and English template filled from the decision's own numbers. Ask Chhatri (N2, BUILT behind `n2_ask_chhatri`) extends it to free questions, grounded in the policy and the decision.

## 6. Where others are ahead today and where we stand

| Area | Current state | Where Chhatri stands |
|---|---|---|
| **Merchant-facing journey** | Several projects show step-by-step flows (Nirdesh, FinSaathi, SAHAAY, Claim Advocate, Praman). | **N1 mini-app** BUILT behind `n1_miniapp`: cover card, coverage explainer, claim tracker, receipt and help, Hindi first, with the grievance and consent screens behind `n5_grievances` and `n6_consents` and Marathi as a draft behind `n8_marathi`. It has not been rehearsed or tried with a merchant |
| **Public demo link** | 11 of the 28 projects had a link that answered at least once on 2 Oct. Chhatri has none | **N7 static build** BUILT: a mock-mode build of the console with a permanent SIMULATED banner. The repo owner deploys it to GitHub Pages or any free static host. No address exists until then |
| **Live AI in the demo** | Several repositories describe a model, but our scan found no AI service calls in their code. Others are live only with a key | **N3, N2, N4** BUILT behind flags: Gemini free tier first, then Sarvam, then templates (N2) or a person (N3). Every reply is labelled LIVE, SIMULATED or FALLBACK (H26). The chains are tested against fakes only. A key counts only after a rehearsal call succeeds on the demo laptop |
| **Explainability** | Sahaj, SAHAAY, Claim Advocate, Resolve OS and Praman trace their reasoning | **K5** explanation card, plus sources (H13) and counterfactuals (H14) on the receipt, are BUILT |
| **Test visibility** | Praman's README states 930. Chhatri's README does not state its counts | Not done: the measured counts are written after the final run. The 2 Oct baseline was backend 1,747 (1,711 fast and 36 slow, 99.7% coverage), frontend 264, infra 118, demo-check 70 of 70. Never rounded up |

## 7. Market facts and our positioning

**The merchant problem.** Earlier merchant plans took 30–60 days per claim (A3). In our replay Chhatri pays 4 simulated minutes after the trigger. A8, A9 and A14 show basis risk or settlement delay in other approaches.

**Why Paytm.** Paytm has, in one place, live sales per shop (1.57 crore device merchants, A1), the settlement rail, the Soundbox, a licensed insurance broking arm (A4) and merchant lending (A5). Financial-services revenue was ₹814 crore in Q1 FY27, up 45% year on year (A2). The existing plan shows merchants buy cover: under ₹2 a day, 2 lakh+ merchants covered (A3).

**What is different.** Parametric income cover exists (A14). As far as we found, our trigger is different: the merchant's own live sales inside the payments app, checked at area level. The settlement link and the lender-decided EDI holiday make it work financially. Hindi explanations make it human. (Note: "Area Income Signal" is our own roadmap idea, not a Paytm product.) No insurer or lender has agreed to anything. A partner insurer and lender will be approached after the hackathon.

## 8. Scan method and limitations

**Method.** We searched GitHub on 1–2 Oct 2026 for public repositories about the Paytm Build for India hackathons (keywords "paytm", "hackathon", "track 2", "financial journeys"). On 2 Oct we read each README, the docs, the AI calls and the tests in the code, and checked every demo link with HTTP requests, twice, a few hours apart. We also read the official Mumbai Track-2 finalist poster (25 teams named; two rivals with public repos, plus ours). Three repositories (JeevanFlow, ClaimSaathi, GrowSAATHI) were added after the first pass. We ran no other team's code or tests.

**What we found.** 28 repositories: 2 state Mumbai Track 2; 3 are from the Delhi edition (Nirdesh, One-Tap Credit, Resolve OS); 1 is Mumbai on another track; 10 state Track 2 without an edition; 8 state neither; 4 were created on the Bengaluru edition date. We found no public results for any edition as of 2 Oct 2026.

**Known limits.** 22 of the 25 Mumbai Track-2 finalist teams have no public code that we could find, so we cannot comment on their approaches. Repositories change: Praman's did on 2 Oct. "Not found" means we did not see it, and we may have missed it. A team's live demo can differ from its repository.

## Open questions

1. Will any rival publish code or a demo before 3 Oct? Should we re-scan on the morning of 3 Oct? Owner: Omkar Kadam.
2. If results are published for any edition, which ideas do the judges credit? Add them here. Owner: Omkar Kadam.
3. H24 is credited to Resolve OS and FinPath AI. What-if sliders and simulators also appear in FINPATH, Sahaj, SAHAAY and Sahayak. Should the credit be widened? Owner: Omkar Kadam.

## Changelog

- 2026-10-03 · v1.6 · Chhatri's own status brought up to the code: the planned features are BUILT behind flags; the capability matrix, the H1 to H26 status columns and section 6 are rewritten; the rival scan itself is unchanged (2 Oct)
- 2026-10-02 · v1.5 · second scan: added the three new repositories (JeevanFlow, ClaimSaathi, GrowSAATHI), Praman's 2 Oct update (README tests 703 to 930), FINPATH, AeroFin AI, Rakshak, AI-CLARITY-LAYER and Clarity; the H13 to H26 table with credits, wave and spec; wave and status for every H idea; capability matrix corrected (area and hospital-cash rows split, FinPath AI and FINPATH separated, wording "not found" instead of "no"); removed the uniqueness claim; fixed Nirdesh demo status, the SetuAI and Soundbox Saathi credits, and the Tailwind row (the mini-app uses it, scoped); linked the rival teardown appendix
- 2026-10-02 · v1.4 · final fact-check: A3 and SEWA timings as sourced, unsourced payout times removed, hedged uniqueness, per-shop payout, scan dates corrected, one individual's handle removed
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned
- 2026-10-02 · v1.1 · fact-check pass: corrected "Pi" references (withdrawn); replaced "Feature ID" column headers with standard section references; clarified feature harvest table.
- 2026-10-02 · v1 · first draft, from a GitHub and live-demo scan on 2 Oct.
