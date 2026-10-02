# Competitive landscape

| | |
|---|---|
| Status | Draft v1 · 2 Oct 2026 |
| Owner | Omkar Kadam |
| Audience | Judges, mentors, the team, rivals; the public may read it, so be factual and generous |
| Related | [Facts and sources](facts-and-sources.md) · [Current-state audit](current-state-audit.md) · [Vision and positioning](../02-product/vision-and-positioning.md) |

## TL;DR

- Merchants today have no cover that pays lost income within hours. Paytm's merchant protection plan shows they will buy cover (A3); earlier plans took 30–60 days per claim. Chhatri pays the same day from sales data.
- Parametric (weather-linked) income cover exists (Riskwolf, SEWA) but has two problems: basis risk (no payout in a real loss) and slow settlement (weeks).
- We found 2 confirmed Mumbai Track-2 projects with public repos, 2 Delhi Track-2 projects, and 11 others with published demos. Among them, Chhatri's automatic claim from the merchant's own sales is unique as far as we could find.
- Rivals' strengths: step-by-step journeys, explainability traces, honest-wording tests, voice-first interfaces, zero-login demos. We close these gaps with N1–N7.
- We adopted H1–H12 ideas from the ecosystem (progress tracker, evidence badges, readiness checklist, deterministic rules, consent design, etc.), crediting sources.

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

**The gap:** merchants lose sales during a shock (monsoon, illness) and need money within hours, not weeks. None of these products pays lost income from the shop's own sales on the same day.

## 2. Track-2 hackathon projects (verified on 2 Oct 2026)

### A. Confirmed Mumbai Track 2

| Project | Team | Repo | Live demo | Test count | Strengths | Overlap with Chhatri |
|---|---|---|---|---|---|---|
| **Praman** | HackOverFlow | [github.com/rithvikshettyy/praman-paytm](https://github.com/rithvikshettyy/praman-paytm) | none found | 703 (README) | Health-claim readiness checklist; deterministic rule engine; honest-wording test; voice in Marathi | Same policy-engine approach; we adopted H4 (honest wording). |
| **Paytm Virasat** | not stated | [github.com/JACELL100/paytm-virasat](https://github.com/JACELL100/paytm-virasat) | none found | not stated | Claims co-pilot after death in family; proof-of-life flow | Different problem (bequest). No overlap. |

### B. Possibly Mumbai Track 2 (not confirmed)

| Project | Repo | Evidence | Caveat |
|---|---|---|---|
| **FinSaathi** | [github.com/Bhumik16/FinSaathi](https://github.com/Bhumik16/FinSaathi) | README: "Paytm Buildathon 2026, Track: AI-Powered Financial Journeys"; created 24 Sep 2026. The name matches the finalist team "FinSaathi" on the poster. | Not confirmed: the repo owner is not the team lead named on the poster, and another public repo has the same name (section E). We do not say this repo is the finalist's. |

### C. Delhi Track 2 (same problem statement, 19 Sep 2026)

| Project | Team | Repo | Live demo | Test count | Strengths | What we learned |
|---|---|---|---|---|---|---|
| **Nirdesh** | — | [github.com/himangshukumbhakar58-cpu/paytm-nirdesh](https://github.com/himangshukumbhakar58-cpu/paytm-nirdesh) | [paytmnirdesh.vercel.app](https://paytmnirdesh.vercel.app) (demo site down 2 Oct) | not stated | Step-by-step journey with progress bar; three-column layout; bilingual (English, Bengali) | H1: journey steps with "you are here". We use this in N1 tracker. |
| **One-Tap Credit** (Team1) | — | [github.com/carbonFibreCode/paytm-one-tap-credit](https://github.com/carbonFibreCode/paytm-one-tap-credit) | [paytm-one-tap-credit.vercel.app](https://paytm-one-tap-credit.vercel.app) | 32 (README) | 14 ordered hard gates as pure functions; affordability-first; explainability trace with counterfactuals; offer frequency capping. | H9: no loan offers during distress (we added X8). Deterministic gate approach for the policy engine (we use K4). |

### D. Other Paytm tracks (reference for pattern ideas)

| Project | Track | Repo | Live demo | Notable ideas | Adopted |
|---|---|---|---|---|---|
| **Resolve OS** | Autonomous AI Teammates | [github.com/sparsh101sparsh/resolve-os](https://github.com/sparsh101sparsh/resolve-os) | [paytm-desk.vercel.app](https://paytm-desk.vercel.app) | Deterministic policy engine where LLM has zero authority over funds; immutable audit log; fixture fallback. | H10 (policy engine); H7 (fallback switch). |
| **Soundbox Saathi** | Merchant Growth AI | [github.com/ShivprasadChinnchole/soundbox-saathi](https://github.com/ShivprasadChinnchole/soundbox-saathi) | not found | Voice-first merchant insights; Sarvam voice library; propose → confirm → execute lifecycle. | Sarvam STT/TTS choice for N4. |

These projects are from different tracks, but their patterns (deterministic engines, voice, fallbacks) influenced our architecture.

### E. Track-2-aligned projects (no edition stated; verified public repos and live demos)

| Project | Repo | Live demo | Strengths | Adopted | Credit link |
|---|---|---|---|---|---|
| **Sahaj** (The NPM Tigers) | [github.com/shiv9956/Sahaj](https://github.com/shiv9956/Sahaj) | [sahaj-web-pi.vercel.app](https://sahaj-web-pi.vercel.app) | Trust receipts (sources and assumptions visible); Hinglish voice; glass-box judge mode; red-team prompt-injection suite. | H2 (evidence trace, "why this amount" with badges); H7 (judge mode). | [Sahaj](https://github.com/shiv9956/Sahaj) |
| **SAHAAY** | [github.com/vishesh1916/sahaay---AI-recovery-agent-](https://github.com/vishesh1916/sahaay---AI-recovery-agent-) | [sahaay-six.vercel.app](https://sahaay-six.vercel.app) | Evidence badges; context reuse across steps; deterministic gap engine. | H2 (source badges in explanations). | [SAHAAY](https://github.com/vishesh1916/sahaay---AI-recovery-agent-) |
| **Claim Advocate** | [github.com/arpit2705/Claim_Advocate](https://github.com/arpit2705/Claim_Advocate) | [claim-advocate-pi.vercel.app](https://claim-advocate-pi.vercel.app) | Policy-grounded claim review; evidence trace; exact plus semantic retrieval; human check of extracted slip data. | H2 (evidence trace); H5 (merchant confirms extracted data before checks run). | [Claim Advocate](https://github.com/arpit2705/Claim_Advocate) |
| **FinPath AI** | [github.com/Sushrut-Kale/paytm](https://github.com/Sushrut-Kale/paytm) | [finpath-ai-three.vercel.app](https://finpath-ai-three.vercel.app) | Goal-first journeys; deterministic readiness engine; **zero-login demo route**. | H6 (zero-login static demo). We build N7 to close this gap. | [FinPath AI](https://github.com/Sushrut-Kale/paytm) |
| **FinSaathi** | [github.com/agniv-dutta/FinSaathi](https://github.com/agniv-dutta/FinSaathi) | [finsaathi-five.vercel.app](https://finsaathi-five.vercel.app) | Health claim assistant; policy Q&A and coverage explainer; claim tracking. | Overlap in scope (health claims) but not in trigger or payout model. | [FinSaathi](https://github.com/agniv-dutta/FinSaathi) |
| **Vanifi** | [github.com/dare-devil-coder/Vanifi](https://github.com/dare-devil-coder/Vanifi) | none found | Ethical credit suppression during distress; Safe-to-Spend signal. | H9 (no loan offers during crisis). | [Vanifi](https://github.com/dare-devil-coder/Vanifi) |
| **COVE2E** | [github.com/sohanpal17/COVE2E](https://github.com/sohanpal17/COVE2E) | none found | Stuck-claim recovery plan; deterministic action gate; outcome verifier. | H10 (deterministic engine). | [COVE2E](https://github.com/sohanpal17/COVE2E) |
| **SetuAI** | [github.com/ronakparmar11/setuai](https://github.com/ronakparmar11/setuai) | [setuai-two.vercel.app](https://setuai-two.vercel.app) | Voice and OCR claim concierge. | N3, N4 (slip reading + voice). | [SetuAI](https://github.com/ronakparmar11/setuai) |
| **Sahayak** | [github.com/ayushraj5634/Sahayak_Paytm](https://github.com/ayushraj5634/Sahayak_Paytm) | [sahayak-sigma-lyart.vercel.app](https://sahayak-sigma-lyart.vercel.app) | Loan-rejection coach; debt-to-income simulator; bilingual. | Different problem (loan rejection). No direct overlap. | [Sahayak](https://github.com/ayushraj5634/Sahayak_Paytm) |

## 3. Capability matrix: how we compare

To understand where Chhatri stands today and after the Oct 2–3 build, here is a feature matrix across competitors:

| Capability | Chhatri (today) | Chhatri (after Oct 2–3) | Praman | One-Tap Credit | Nirdesh | Sahaj | Claim Advocate | FinPath AI | SAHAAY |
|---|---|---|---|---|---|---|---|---|---|
| Automatic claim (no form) | Yes | Yes | No | No | No | No | No | No | No |
| Merchant product (not officer tool) | No | Yes (N1) | No | No | No | No | No | Yes | No |
| Links to lending (EDI holiday) | Yes | Yes | No | No | No | No | No | No | No |
| Walks health-claims example end-to-end | Partial (slip reading) | Yes (N3 + hospital-cash) | Partial | Partial | Partial | No | Partial | Partial | No |
| Live AI in demo (not word list) | Partial (Sarvam, with a key) | Yes (N2, N3, N4) | No | No | No | Partial | Partial | Partial | Partial |
| Indic voice (Hindi, Marathi, Bengali) | Partial (Hindi via Sarvam, with a key) | Yes (N4 Hindi; N8 Marathi if time) | Yes (Marathi) | No | Yes (Bengali) | Yes (Hinglish) | No | Yes (5 languages) | No |
| Deterministic money decisions | Yes | Yes | Yes | Yes | No | Yes | No | Yes | Yes |
| Audit trail (hash-chained or immutable) | Yes | Yes | Partial | Yes | Partial | Yes | No | No | Yes |
| Public live demo (zero-login) | No | Yes (N7) | No | Yes | No (404) | Yes | Yes | Yes | Yes |
| Published test count | Partial (70 demo checks) | Yes (1,747 backend + 264 frontend + 70 demo) | Yes (703) | Yes (32) | No | Partial (39+) | No | Yes (25 + 8) | No |

**Legend:** Yes = shipping; Partial = partial or simulated; No = not found in code or README.

**Key observations:**
- Chhatri's automatic claim from merchant sales is unique.
- After Oct 2–3, Chhatri will have all 10 capabilities to some degree.
- Rivals lead on merchant journey UI (Nirdesh, FinPath AI) and voice breadth (FinPath AI: 5 languages); we close this with N1 and N4.
- Test counts vary widely. Praman's README states 703, the most among the rival projects we found. Chhatri measures 1,747 backend tests today, plus 264 frontend tests (262 passing until X1), 118 infra tests and 70 demo checks.

## 4. Feature harvest: what we learned and adopted

From the ecosystem scan, we adopted 12 ideas, crediting source projects:

| Idea (source) | What Chhatri does | Impact |
|---|---|---|
| Step-by-step journey (Nirdesh, SAHAAY, FinSaathi) | **N1 claim tracker**: each step (Detected → Checked → Decided → Paid → EDI holiday) shows state, reason, next step and ETA. | Makes the claim journey transparent and builds confidence. |
| Evidence trace with badges (Claim Advocate, SAHAAY, Sahaj) | **K5 explanation card**: "why this amount" shows the rule, numbers and source badges (sales index, alert, KYC, slip). Renders from decision facts only. | Stops blame and dispute. Grounded in what the merchant can verify. |
| Payout receipt (Sahaj's trust receipt, AI-CLARITY-LAYER PDF statement) | **N1 receipt**: decision id, rules version, formula, data sources, audit hash prefix, grievance path. Printable to PDF. | Creates a paper trail the merchant can keep and show to a lender. |
| Honest-wording test (Praman) | **X7 test**: fails if a template uses false-promise words (e.g. "guaranteed", "100%"), claims money not in decision facts, or says "paid" before a payout record exists. | Guards against false hope or misleading language. |
| Readiness checklist (FinPath AI, FINPATH) | **N3 slip pre-check**: show extracted fields to the merchant; ask retake if unclear. Three-item checklist (photo readable, name matches KYC, dates match silent day) before running checks. | Prevents wasted cycles on blurry photos or data mismatches. No false "readiness score". |
| Zero-login demo (FinPath AI) | **N7 static demo**: mock-mode console at a public URL, opening straight into the monsoon replay with a persistent "SIMULATED demo" banner. | Judges and mentors can see the product without credentials. Offline-safe (no backend needed). |
| Glass-box judge mode with fallback (Sahaj, Resolve OS) | **X6 provider panel** (on-demo-stage only): each AI component shows LIVE, SIMULATED or FALLBACK. "Force fallback" switch shows degradation on purpose. | Transparency about what is working and what is not. Contingency for live failures. |
| Real operational counts (Praman, Resolve OS ops desk) | **K8 ops strip**: open cases by state, oldest SLA clock, share decided automatically vs by a person, today's payouts by zone. Counted from DB only, never projected. | Audit trail + operational discipline. No made-up numbers. |
| No loan offers during distress (Vanifi, One-Tap Credit) | **X8 rule**: no loan, top-up or cross-sell message while an alert covers the zone, a claim or dispute is open. Proactive messages capped per day. A test enforces it. | Ethical credit suppression. Builds trust when the merchant is vulnerable. |
| Deterministic engine, LLM no authority over money (Resolve OS, One-Tap Credit, Praman) | Already **K4 policy engine**: deterministic checks with thresholds in `rules.yaml`. The only path to money. | Auditability, predictability, regulatory defensibility. |
| Bilingual templates, not LLM translation (Nirdesh, Soundbox Saathi) | Already **message catalogue**: Hindi + English, filled from decision facts. N8 adds Marathi via the same catalogue. | Consistency and control over every word. No surprises from translation models. |
| Visible, measured test counts (Praman) | After X1–X8: publish the measured counts. Never round up. Show which pass and which are planned. | Credibility with judges who read the code. Shows work. |

**Ideas we did not adopt** (and why):

| Idea | Why not | Alternative we chose |
|---|---|---|
| A numeric 0–100 readiness score (for slip pre-check) | False precision and can mislead. | N3: binary checklist (photo readable, name matches, dates match) before running checks. Qualitative, not scored. |
| Multi-agent orchestration or vector-DB RAG | Policy wording corpus is small (12 clauses). Clause-ID grounding is simpler, testable and faster than RAG. | N2: direct LLM grounding to clause IDs in the decision facts. Same-day queries, no vector ops. |
| Blockchain proof-of-life (for death-claim scenarios) | Out of scope for income cover. | None; not adopted. |
| Paid-tier AI inference APIs | Free stack only: Gemini free tier and Sarvam free credits. | Sarvam + Gemini + browser fallbacks. |
| Recharts, Tailwind or other CSS frameworks | Keep the current stack: plain CSS tokens and react-leaflet. Smaller bundle, offline-safe, Devanagari-friendly. | Existing CSS and react-leaflet 5. |

## 5. Where Chhatri is different (honest novelty)

**Unique trigger:** Chhatri measures the loss from the merchant's own sales (not an area rain gauge or a crop yield model) and pays the same merchant. The mechanism:

- Every merchant has daily expected sales (from their own history).
- A weather alert covers the zone for the whole window (IMD-style; simulated in the prototype).
- At the zone's 3rd consecutive hour below 50% of expected sales, with the window below the model's conformal lower bound and at least 20 shops in the index, the trigger fires.
- Each insured shop in that zone is paid ½ × its own expected day × the drop %, capped at ₹2,500 a day.
- At area level, the loss cannot be faked: 20+ shops must agree to the drop. One shop's slow day alone does not pay.

This is new. Riskwolf uses an external index (A14); SEWA and crop insurance use rainfall or yield (A8, A9).

**Settlement-linked payout:** the money credits with the next settlement, so the merchant can use it for the day's operations or the loan instalment, instead of waiting weeks (compare SEWA, A9).

**EDI holiday:** if an approved payout happens, Chhatri requests the lender's pre-agreed EDI holiday for the next instalment. The lender's policy decides (loan is active, not in arrears, holiday allowance not used up). No instalment is paused by Chhatri alone; the lender controls this.

**Same-day explanations in Hindi.** Today the "why did I get this much?" answer is a Hindi and English template filled from the decision's own numbers. Ask Chhatri (N2, planned) extends this to free questions, grounded in the policy and the decision.

## 6. Where others are ahead today and how we close the gap

| Area | Current state | How Chhatri closes it |
|---|---|---|
| **Merchant-facing journey** | Praman, Nirdesh, FinSaathi, SAHAAY, Claim Advocate show step-by-step flows. Chhatri's console is a claims-officer tool. | **N1 mini-app** (P0 Oct 2): merchant-facing screen for cover explainer, consent, claim tracker, grievance ladder, all in Hindi-first. |
| **Live demo URL** | 11 projects have public URLs; Chhatri's prototype has none. | **N7 static demo** (P0 evening Oct 2): GitHub Pages / Vercel build with the console in mock mode. Permanent "SIMULATED" banner. |
| **Live AI in the demo** | Most projects' repos say "LLM", but many rely on word lists or do not set API keys. | **N2 grounded assistant** (P0 Oct 2): Gemini free tier → Sarvam chat → templates. Only says money amounts that are in the decision. **N3 slip reading** (P0 Oct 2): Gemini vision or Sarvam Vision with a pre-check. **N4 voice** (P0 Oct 2): Sarvam STT/TTS or browser Web Speech. |
| **Explainability** | Sahaj, SAHAAY, Claim Advocate, Resolve OS trace the reasoning. | **K5 explanation card** already in the console (K8); we surface it in N1 receipt and Ask Chhatri answer. Source badges (H2). |
| **Test visibility** | Praman states 703; others less clearly. Chhatri's README does not state its 1,700+ tests. | After X1: README and pitch show **backend 1,747 (99.7%), frontend 264, infra 118, demo-check 70/70**. Never round up. |

## 7. Market facts and our positioning

**The merchant problem:** earlier merchant plans took 30–60 days per claim (A3). Chhatri pays the same day. (A8, A9, A14 show basis risk or settlement delay.)

**Why Paytm:** Paytm has, in one place, live sales per shop (1.57 crore device merchants, A1), the settlement rail, the Soundbox, a licensed insurance broking arm (A4) and merchant lending (A5). Financial-services revenue was ₹814 crore in Q1 FY27, up 45% year on year (A2). The existing plan shows merchants buy cover: under ₹2 a day, 2 lakh+ merchants covered (A3).

**Honest novelty:** parametric income cover exists (A14). Our trigger is new: the merchant's own live sales inside the payments app, checked at area level to prevent gaming. The settlement link and the EDI holiday make it work financially. Voice-first explanations in Hindi make it human. (Note: "Area Income Signal" is our own roadmap idea, not a Paytm product.)

## 8. Scan method and limitations

**Method:** GitHub search on 1–2 Oct 2026 for repos created from 15 Sep 2026 onward with the keywords "paytm", "hackathon", "track 2" or "financial journeys". HTTP checks of live demo URLs on 2 Oct 2026. README parsing for edition, track, team name, test counts and feature claims. A manual review of the official Mumbai Track-2 finalist poster (25 teams named; 2 rivals with public repos, plus ours).

**What we found:** 2 confirmed Track-2 projects in Mumbai (Praman, Virasat); 2 in Delhi (Nirdesh, One-Tap Credit); 11 others with published demos; 4 from Bengaluru (a different problem statement, Mar 2026). No public results or "winner" announcements found for any edition as of 2 Oct 2026.

**Known limitation:** 22 of the 25 Mumbai Track-2 finalists have not published their code. We cannot comment on their approaches.

## Open questions

1. Will any rival project release code or demos between now and 3 Oct? Should we update this landscape scan? Owner: Omkar Kadam.
2. After the hackathon, which other projects will publish their approach? Who will the judges credit? Owner: Omkar Kadam.

## Changelog

- 2026-10-02 · v1.4 · final fact-check: A3 and SEWA timings as sourced, unsourced payout times removed, hedged uniqueness, per-shop payout, scan dates corrected, one individual's handle removed
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned
- 2026-10-02 · v1.1 · fact-check pass: corrected "Pi" references (withdrawn); replaced "Feature ID" column headers with standard section references; clarified feature harvest table.
- 2026-10-02 · v1 · first draft, from a GitHub and live-demo scan on 2 Oct.
