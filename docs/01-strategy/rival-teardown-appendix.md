# Rival teardown appendix

| | |
|---|---|
| Status | Draft v1.1 · 3 Oct 2026 · the scan is of 2 Oct; Chhatri's own status is of 3 Oct |
| Owner | Omkar Kadam |
| Audience | Judges, mentors, the team. The public may read this page, so it is factual and generous |
| Related | [Competitive landscape](competitive-landscape.md) · [Requirements traceability matrix](requirements-traceability-matrix.md) · [Problem statement analysis](problem-statement-analysis.md) · [PRD §3](../02-product/prd.md) · [Facts and sources](facts-and-sources.md) |

## TL;DR

- From a scan on 2 Oct 2026 we read 28 public repositories that relate to the Paytm Build for India hackathons. Section 2 has one row per project. Section 3 has a short note on the nine closest projects.
- Most of these projects help a person understand, check, file or dispute something. Several work on health or insurance claims: Praman, Claim Advocate, SAHAAY, ClaimSaathi, FinSaathi (agniv-dutta) and COVE2E. In the repositories we read, we did not find one that starts a claim and pays it from the user's own sales or data. We may have missed one, and 22 of the 25 Mumbai Track-2 finalist teams have no public code that we could find.
- What we took from them is listed as H1 to H26 in the [competitive landscape](competitive-landscape.md#4-feature-harvest-what-we-learned-and-adopted). Each row below names the ideas by H-id. What we looked at and did not take is in section 4.
- Where they are ahead today: public demo links, merchant-facing screens and live AI in the demo. Chhatri has no public demo link yet. N7 builds a static copy, and the repo owner has to deploy it.
- We did not run any other team's code or tests. Test counts are as each project states them. Demo link status is from HTTP checks on 2 Oct.

## 1. Method and limits

| Topic | What we did, and what it does not tell you |
|---|---|
| Scan | On 2 Oct 2026 we searched GitHub for public repositories about the Paytm Build for India hackathons (keywords "paytm", "hackathon", "track 2", "financial journeys"). We read each README, the docs, the AI calls and the tests in the code. Three repositories (JeevanFlow, ClaimSaathi, GrowSAATHI) were added after the first pass and are included. |
| Edition and track | Taken from the README or plan text. Where it is silent we write "not stated". A creation date is not proof of an edition. |
| Demo links | Two HTTP checks on 2 Oct, a few hours apart. A timeout can be a network problem on our side, so re-check a link before you quote it. |
| Tests | The count each project states in its README or docs. Where a project states none, we say what we found. We ran none of them. A test count measures effort, not quality, in either direction. |
| "Not found" | Means we did not see it in the repository. We may have missed it, or it may exist only in the team's demo. |
| Change | Repositories move. Praman's repository was updated on 2 Oct: its README test count went from 703 to 930 during the day. Numbers here are as read on 2 Oct. |
| Names | Project and team names only. No individuals. We start with strengths, compare on facts and say "overlap", not "threat". |
| Results | We found no public results for any edition as of 2 Oct 2026. "Winner Edition" in Sahaj's README title is the title of its build prompt, not a result. |

Legend for the demo column: **Both OK** means the link answered in both checks. **Mixed** means it answered in one check and timed out in the other. **404** means the link returned "not found". **None found** means the repository lists no demo address.

## 2. One row per project

Columns: project and last push · edition and track · what it does · AI use · demo link on 2 Oct · tests · standout idea · main limitation · what Chhatri adopted (H-id) or how it covers the gap.

### 2.1 Mumbai edition, Track 2 (stated in the README)

| Project | Edition and track | What it does | AI use | Demo, 2 Oct | Tests | Standout idea | Main limitation | Chhatri: adopted, or how it covers the gap |
|---|---|---|---|---|---|---|---|---|
| [Praman](https://github.com/rithvikshettyy/praman-paytm) (team HackOverFlow)<br>last push 2 Oct | Mumbai edition, Track 2 (README) | Health-claim readiness assistant on WhatsApp and web. Says "file", "do not file yet" or "file with a known deduction". Routes a complaint to the insurer, lender or distributor with that party's escalation ladder | Sarvam for chat, document reading, speech and translation. Rules, routing and bill-head lookup are code | None found | README states 930 tests, no network (703 earlier on 2 Oct) | Pure rule engine. A verified-by field on every rule, unchecked values badged. Respondent router with response clocks | Advises and drafts: its README says nothing is filed or sent. Lending and motor rule sets are listed as next steps | H4, H8, H10, H12, H13, H15, H17, H22. Chhatri starts the claim and pays an income benefit, and requests the lender's EDI holiday |
| [Paytm Virasat](https://github.com/JACELL100/paytm-virasat)<br>last push 25 Sep | Mumbai edition, Track 2 (README) | Legacy vault and claims co-pilot for a family after a death: find assets, set nominees, prepare claim packs | Groq model co-pilot with tool calling. Whisper and Sarvam for voice. Tesseract for scans | None found | Not stated. About 80 test functions in the repo (42 backend, 38 contracts), none in the front end | Claim-pack PDFs pre-filled for each institution. Proof-of-life check | A different journey (after a death, not a living merchant's income). Asset discovery uses seed data | None adopted. Chhatri's tamper evidence is a hash-chained database log (K7), not a blockchain registry |

### 2.2 Track 2 stated, edition not stated

| Project | Edition and track | What it does | AI use | Demo, 2 Oct | Tests | Standout idea | Main limitation | Chhatri: adopted, or how it covers the gap |
|---|---|---|---|---|---|---|---|---|
| [FinSaathi](https://github.com/Bhumik16/FinSaathi) (a repo with this name; not confirmed as the finalist team's; another is in 2.5)<br>created 24 Sep | README: "Paytm Buildathon 2026", Track 2. Edition not stated | Front-end prototype of a multi-agent "journey agent" for insurance, lending and fintech, in English, Hindi and Marathi | The README describes agents and retrieval. We found no AI service calls in the code (scripted keyword replies) | None found | No test files found | Agent activity drawer and a decision panel | A prototype with no back end: checks and journeys are written in advance | None adopted. Marathi comes through our message catalogue (N8). The policy engine makes the decisions |
| [Sahaj](https://github.com/shiv9956/Sahaj) (team The NPM Tigers)<br>last push 19 Sep | README: Track 2. Edition not stated | Voice-first Hinglish "journey engine" for education loans and insurance discovery | Sarvam for speech, document reading and chat. Cognee memory. Pure-code calculators and a grounding gate | [Live](https://sahaj-web-pi.vercel.app), both OK | Phase reports state 54 passing tests (39 in an earlier report). Its eval report states 96.0% intent accuracy on 60 synthetic scenarios and 10 of 10 red-team vectors blocked, self-reported | Trust receipt on every answer. Confirmation chips for spoken amounts. Tappable jargon. Next-best-action bar. "Forget everything" | A mock Paytm connector and synthetic data. It guides a person and does not start or pay claims | H2, H3, H7, H18, H20, H21, H23, H25 |
| [SetuAI](https://github.com/ronakparmar11/setuai)<br>last push 25 Sep | README: Paytm AI Hackathon 2026, Track 2 | Front-end design for four journeys (understand, borrow, protect, manage) with a copilot, claim readiness and coverage views | None found in the code. The copilot, scan and voice screens show fixed responses | [Live](https://setuai-two.vercel.app), mixed | No test files found | Confidence label and proof lines under each answer. Waiting-period countdown | A design prototype with no back end | None adopted. Chhatri's slip reading (N3) and voice (N4) run on live adapters with labels (H26) |
| [SAHAAY](https://github.com/vishesh1916/sahaay---AI-recovery-agent-)<br>last push 25 Sep | README: Track 2 | Gap and recovery agent for a medical or other emergency: reads policy and bill, works out the uncovered gap by rule, carries verified data forward ("FlowPass") | Groq-hosted models read documents. LangGraph orchestration. The gap maths is a rule engine | [Live](https://sahaay-six.vercel.app), both OK | 4 test files; the README states no count | Seven evidence states on every figure. Recovery what-if slider | Financial data is simulated. It shows what a claim leaves uncovered and does not pay | H1, H2 |
| [FINPATH](https://github.com/Rushilp21/Paytm-Hackathon---GDuo) (not FinPath AI)<br>last push 27 Sep | README: the "AI-Powered Financial Journeys" track | Flutter app: life goal, profile, affordability, document review, application or claim draft, simulated tracker, human support | Gemini through a server proxy, with local fallbacks. EMI and affordability are code | None found | README states 25 Flutter tests and 8 backend smoke checks | Review dialog before extracted data is used. Consent toggles with an activity log. Scam-message patterns. Five language options | General personal finance, not merchant income. Its verification note says live Gemini was not tested because no key was supplied | H5, H15, H19, H23 |
| [Claim Advocate](https://github.com/arpit2705/Claim_Advocate)<br>last push 19 Sep | Track 2 (its plan.md). Edition not stated | Policy-grounded review of a health claim before filing, and of a rejection afterwards, with a drafted appeal letter | Groq for every model call. Rules and a decision validator in Python. A text sanitiser against prompt injection | [Link](https://claim-advocate-pi.vercel.app), mixed | 14 test files, about 100 test functions; the README states no count | Evidence chain in every response (verdict, clause, fact, document). Adversarial prompt-injection test. Agreement score labelled "not a probability" | Medical claims only (its code says so). One model provider. English only. No payout or lending | H2, H5, H14, H16. Chhatri pays the claim and requests the lender's EDI holiday |
| [Sahayak](https://github.com/ayushraj5634/Sahayak_Paytm)<br>last push 19 Sep | README: Track 2 | Loan-rejection coach: explains a rejection through debt-to-income, offers three loan sizes and a 90-day recovery plan, in English and Hindi | None found. The chat is rule-based pattern matching | [Live](https://sahayak-sigma-lyart.vercel.app), both OK | No test files found | Debt-to-income what-if slider. Kind reframing of a rejection | Loans only. No insurance or claims | None adopted. No overlap with income cover |
| [COVE2E](https://github.com/sohanpal17/COVE2E)<br>last push 24 Sep | README: Track 2 | Stuck-claim recovery for insurance: finds why a claim is stuck with a seven-step check, plans next steps behind an action gate, verifies the outcome | Sarvam for chat and speech, with deterministic fallbacks | None found | README states 25 tests | Deterministic investigation. Action gate (safe, confirm, escalate, deny). Importable workflow templates | Insurance claims only; no lending or fintech link. Best results need a Sarvam key | H10 (the engine is the only path to money, ADR 0001) |
| [AeroFin AI](https://github.com/BhaskarShah05/paytm-aerofin-ai)<br>last push 15 Sep | README: the "AI-Powered Financial Journeys" track | Front-end mock-up of a "browser agent" that walks a health claim and an education loan step by step | The README describes an LLM agent and OCR. We found no AI service calls, only browser speech output | 404 in both checks (listed address) | No test files found | Jargon buster with an out-of-pocket calculator. Human decision gates before key choices | A design prototype with scripted steps and no back end | H20 |
| [Clarity](https://github.com/anmoltyagi18/clarity)<br>last push 12 Sep | README: the "AI-Powered Financial Journeys" track | Debt-exposure checker for a loan or BNPL application: finds EMI and BNPL obligations in transaction text, gives a verdict | None: rules and arithmetic. Its data are synthetic presets | None found | No test files found | Verdict badge with a plain-text explanation. One-click "safe amount" | Lending only. Fixed thresholds | None adopted. No overlap with income cover |

### 2.3 Delhi edition

| Project | Edition and track | What it does | AI use | Demo, 2 Oct | Tests | Standout idea | Main limitation | Chhatri: adopted, or how it covers the gap |
|---|---|---|---|---|---|---|---|---|
| [Nirdesh](https://github.com/himangshukumbhakar58-cpu/paytm-nirdesh)<br>last push 14 Sep | Delhi edition, Track 2 (README) | Three scripted journeys (lending, insurance claim guidance, spending) with a progress bar and a chat sidebar, in English and Bengali | The README lists Sarvam, Cognee and n8n. We found no AI service calls (regex parsing and scripted text) | [README link](https://paytmnirdesh.vercel.app) answered in our first check. The repo homepage link returned 404 | No test files found | Step-by-step journey with "you are here". Three-column layout | A scripted prototype: data and calculations are fixed, no back end | H1, H11 |
| [One-Tap Credit](https://github.com/carbonFibreCode/paytm-one-tap-credit) (Team1)<br>last push 19 Sep | Delhi edition, Track 2 (README) | Decides at payment time whether to show a pre-approved credit offer: 14 ordered gates as pure functions, affordability first, an explanation for every decision, including staying silent | Sarvam only for nudge copy, with validation and caching. None in the decision | [Link](https://paytm-one-tap-credit.vercel.app), mixed | README states 32 tests | Counterfactual in the trace. AI copy rejected if it invents a number. Frequency cap on offers | One moment of a lending journey, on synthetic data. No claims, documents or voice | H9, H10, H14, H17 |
| [Resolve OS](https://github.com/sparsh101sparsh/resolve-os)<br>last push 19 Sep | Delhi edition (19 Sep 2026). Track "Autonomous AI Teammates" (README) | Support desk for merchant settlement, refund and device issues over WhatsApp in Hinglish. Escalates to people when policy says no | Sarvam 105B for intent and replies. A deterministic engine holds every money limit. A fixture planner runs without a key | [Live](https://paytm-desk.vercel.app), both OK | README states 39 passing tests, 19 of 19 rubric checks and 40 policy benchmarks | "Zero fund rights" for the model. SHA-256 policy tokens burned on use. Judges can change the data and watch the policy react | A different domain (support operations). WhatsApp text is the only inbound channel | H7, H8, H10, H24, H25 |

### 2.4 Mumbai edition, another track

| Project | Edition and track | What it does | AI use | Demo, 2 Oct | Tests | Standout idea | Main limitation | Chhatri: adopted, or how it covers the gap |
|---|---|---|---|---|---|---|---|---|
| [Soundbox Saathi](https://github.com/ShivprasadChinnchole/soundbox-saathi)<br>last push 1 Oct | Mumbai edition, Merchant Growth AI track (README) | Voice-first business partner for merchants: daily summary, lapsed customers, low stock, slow hours. Proposes actions and waits for a yes | Gemini with tool calling and an offline fallback "brain". Sarvam for Hindi and Marathi voice | None found (runs locally) | No Python tests; 22 lines of Flutter widget tests | Numbers come only from tools, and the model explains. Propose, confirm, execute lifecycle. The demo never breaks | A different track. Every action (offers, reorders, loan check) is simulated | H11, H17, H26 |

### 2.5 Edition or track not stated in the repository

| Project | Edition and track | What it does | AI use | Demo, 2 Oct | Tests | Standout idea | Main limitation | Chhatri: adopted, or how it covers the gap |
|---|---|---|---|---|---|---|---|---|
| [FinPath AI](https://github.com/Sushrut-Kale/paytm) (not FINPATH)<br>last push 25 Sep | Not stated | Goal-first platform: a plain-language goal becomes a mission with a five-factor readiness score, next-best-action rules and document OCR with user confirmation | Gemini with a keyword fallback. The readiness and next-action engines are rules | [Live](https://finpath-ai-three.vercel.app), both OK | README states 18 passing tests (backend) | Zero-login demo route. Readiness report with "what is affecting" and "next improvement" | Education-loan example. We saw no insurance-claim example in the demo. English only | H5, H6, H15, H24 |
| [FinSaathi](https://github.com/agniv-dutta/FinSaathi) (health claims; another repo with this name is in 2.2)<br>last push 24 Sep | "Paytm Build for India Hackathon" (README). Track not stated | Health-claims assistant UI: policy upload, plain-language breakdown, claim analysis, document checklist, escalation guidance, claim tracker, policy comparison | Groq-hosted model with a keyword fallback | [Live](https://finsaathi-five.vercel.app), both OK | No test files found | Nine-step claim journey with a progress bar. Deduction explainer | Policy and tracker data are sample data | H1 |
| [Vanifi](https://github.com/dare-devil-coder/Vanifi)<br>last push 13 Sep | Not stated | Voice copilot for everyday money in Indian languages: safe-to-spend, a "pulse" score, a loan key-fact-statement flow, no loan offers when the user is stressed | Gemini and Sarvam voice, with grounded fallbacks. The money maths is code | None found | README states 15 test assertions (financial engine) | Loan offers suppressed in the decision layer, not in the screen | Banking and loans are mocked. No insurance product | H9 |
| [Rakshak](https://github.com/Akataruka/paytm-hackathon)<br>last push 19 Sep | Not stated | Counter-fraud check for a merchant: verifies a payment against the ledger instead of a screenshot. Silence detection, field verification | Gemini for speech and explanations. Code rules decide. Cognee is optional | [Live](https://paytm-hackathon-lake.vercel.app), both OK | No test files found | Every external call returns data, a mode and a fallback reason. Rules decide, the model only explains | Merchant payment fraud, probably another track. Integrations are stubbed | H26 |
| [AI-CLARITY-LAYER](https://github.com/Sahajananda-ai/AI-CLARITY-LAYER)<br>last push 19 Sep | Not stated | Browser-only explainability layer for a loan and an insurance journey: eligibility score, document validator, notices in English, Hindi and Kannada, PDF statement | None. Deterministic rules in the browser | None found | No test files found; the README says checks were manual | Seven named document checks with an explanation each. On-device PDF statement | No back end. Document checks are heuristic | H3 |
| [JeevanFlow](https://github.com/Medhavi1906/JeevanFlow)<br>last push 25 Sep | Not stated. README: "AI-Powered Financial Journey & Decision-Support Platform" | Life-event decision support (wedding, education, house, medical, job loss): health score, funding gap, runway, what-if, first-aid steps | A small scikit-learn intent classifier. No language model. Explanations are templates | None found (local run) | No test files found (one placeholder) | Plain "first aid" actions for each life event. Runway in months | General personal finance. Six fixed journeys. No stored profiles | None adopted. No overlap with income cover |
| [ClaimSaathi](https://github.com/buildwithshikhar/paytmbuildforbharat)<br>last push 16 Sep | Not stated. No README. The repo is named for Paytm Build for India | Coverage Q&A on one preloaded health policy. Finds clauses, checks waiting periods in code, answers with page and clause citations | Claude for the final answer. Local embeddings. Dates and months computed in Python | None found (a free-tier Render config exists, no address) | One test file, about 11 tests; no README | Waiting-period arithmetic owned by code, not the model. Every answer cites page and clause. Refuses below a relevance score | One policy, no upload, no claim submission, no officer or lender side | None adopted (found on 2 Oct). It shares the principle behind H10 and H17 |
| [GrowSAATHI](https://github.com/ShivamNishad999/paytm-financial-intelligence-platform)<br>last push 24 Sep | Not stated. README: "Paytm Hackathon Final Round" | Flutter app for merchant growth: dashboard, insights, action centre, campaigns, chat | None in the code: rule-based keyword replies | None found | No test files found | Demo and live mode toggle with a colour-coded status | Growth analytics, not claims. No back end in the repo | None adopted. Its demo and live toggle is the same idea as our X6 labels, which were already planned |

### 2.6 Created on the Bengaluru edition date (21 Mar 2026): a different problem statement

The Bengaluru tracks were "AI for Paytm Users" and "AI for Small Businesses". These four repositories were created on 21 Mar 2026, the date of that edition. Their READMEs do not state the edition. None is a financial-journey assistant.

| Project | Edition and track | What it does | AI use | Demo, 2 Oct | Tests | Standout idea | Main limitation | Chhatri: adopted, or how it covers the gap |
|---|---|---|---|---|---|---|---|---|
| [Vyapaar Saathi](https://github.com/NikhilSetty/PaytmHackathon)<br>last push 21 Mar | Not stated | Voice-first inventory demand tracker for shops, in Hinglish | Faster-Whisper for speech and a local Qwen model through Ollama | None found | No test files found (the README lists four manual phrases) | A fully local voice pipeline | Inventory, not a financial journey | None adopted |
| [SahayAI](https://github.com/drraghavendra/paytm-hackathon)<br>last push 21 Mar | Not stated | WhatsApp voice assistant for small e-commerce sellers: invoices, reminders, GST, ONDC listing | Groq models and Sarvam speech | None found | No test files found | Voice note in, voice reply out, in 11 languages | GST, financing and ONDC steps are mocked | None adopted |
| [Smart Receivables Recovery](https://github.com/EswarDivi/PaytmHackathon)<br>last push 21 Mar | Not stated | Matches invoices to payments and phones late payers | Gemini for invoice reading. OpenAI voice for calls | None found | No test files found | A complete sample flow | Needs paid APIs. English only | None adopted |
| [SMB virtual COO](https://github.com/axvrma/paytm-hackathon) (Paytm Business Shield)<br>last push 21 Mar | Not stated | Six-agent dashboard that gives three recommendations for a shop | Gemini, with canned answers as the fallback | None found | No test files found | Scout agents feeding one synthesiser, with a "devil's advocate" risk view | Data are fixed in the code | None adopted |

### 2.7 Notes on the demo links

- **Both OK (7):** Sahaj, Resolve OS, SAHAAY, Sahayak, FinPath AI, FinSaathi (agniv-dutta), Rakshak.
- **Mixed (3):** One-Tap Credit, SetuAI and Claim Advocate answered in the first check and timed out in the second. Re-check before you quote them.
- **Nirdesh:** the address in its README answered in our first check. The homepage link on the repository returned 404.
- **AeroFin AI:** the listed address returned 404 in both checks.
- **Chhatri:** no public link yet. N7 needs the repo owner to deploy a static build, and this page does not claim an address exists.

## 3. The closest projects

These nine overlap most with Chhatri or taught us the most. Each note says what the project is, what is strong, what we took and where Chhatri differs.

### 3.1 Praman (team HackOverFlow)

- **What it is.** An assistant for policyholders and borrowers on WhatsApp and the web, in the user's language. Before a health claim is filed it says whether the claim will be stopped, delayed or cut, and why. When something has gone wrong it works out who owes the answer (the insurer, the lender or the distributor) and drafts the letter to them. A console counts, from recorded events, how many cases needed the distributor.
- **Strong.** A rule engine with no network, model or clock. A verified-by field on every rule and regulatory value, and a "Not yet verified" badge until a person checks it. A confidence gate: below the threshold it asks, it does not assume. A checklist where each photo ticks a slot. Marathi voice. Consent, masking and "delete everything". A test that fails if wording says "filed". The README states 930 tests.
- **What we took.** Source badges on every number (H13). The document-type check and "ask, don't assume" (H15). Clause citations (H17). The respondent router with response clocks (H22). The honest-wording test (H4, X7), counts from events (H8) and visible test counts (H12). The pure-rule principle is shared with K4 (H10).
- **Where Chhatri differs.** Praman advises and drafts, and its README says nothing is filed or sent. Chhatri starts the claim itself from the merchant's own sales, pays an income benefit, covers illness with one photo and requests an EDI holiday from the lender. Its lending and motor rule sets are listed as next steps in its README, and its coverage corpus ships with one example policy.
- **Check before quoting.** The repository was created on 30 Sep and updated on 2 Oct, and the test count changed during the day. No public demo link. Praman is the closest overlap with Chhatri in the understand, submit and resolve stages of the track example.

### 3.2 Sahaj (team The NPM Tigers)

- **What it is.** A voice-first Hinglish "journey engine" for first-time borrowers and their families, covering education loans and insurance discovery.
- **Strong.** A trust receipt on every answer: sources, version, rules fired, assumptions. Confirmation chips so a spoken amount is checked before it is used. A tappable jargon lens. A next-best-action bar on every turn. A "forget everything" purge. A judge mode, and a chaos toggle that shows graceful degradation. A published evaluation in its repository.
- **What we took.** Receipts and "why" with sources (H2, H3). The provider panel and fallback switch (H7). Confirmation chips (H18). The jargon lens (H20). The next-action bar (H21). The consent activity log and "forget my slip" (H23). A published evaluation, shown only once measured (H25).
- **Where Chhatri differs.** Sahaj helps a person understand and choose, on a mock Paytm connector. It does not start or pay a claim. In Chhatri the policy engine decides on the merchant's own data and the app explains the decision.
- **Check before quoting.** Test count: its phase reports state 54 (39 in an earlier one). The evaluation figures are self-reported and we did not re-run them. "Winner Edition" in its README title is not a result.

### 3.3 SAHAAY

- **What it is.** An agent for the money side of a medical or other emergency. It reads a policy and a bill with a language model, works out the uncovered gap with a rule engine (proportionate deductions, sub-limits, co-pay), and guides funding. "FlowPass" carries verified data forward so the user does not type it twice.
- **Strong.** Seven evidence states on every figure (verified, extracted, user-provided, estimated, conflicting, needs review, missing). A clean split between the model that reads and the rules that calculate. Consent toggles and Hindi voice input. A live demo.
- **What we took.** Step-by-step journeys (H1) and source badges (H2).
- **Where Chhatri differs.** SAHAAY shows what a claim leaves uncovered and bridges it with funding. Chhatri pays an income benefit by rule and shows the source of every number (H13).
- **Check before quoting.** Financial data in the demo are simulated. The repository has four test files and no stated count.

### 3.4 Claim Advocate

- **What it is.** A review of a health claim before it is filed and after it is rejected, with a drafted appeal letter. It works only on medical claims, and its code says so.
- **Strong.** Model reasoning is followed by deterministic validation of dates, limits and quotes. A sanitiser wraps untrusted text before a model sees it, with an adversarial test. Every response carries an evidence chain from verdict to clause to fact to document. Retrieval combines exact clause lookup with semantic search. Its agreement score is labelled "not a probability".
- **What we took.** The evidence chain and the counterfactual idea (H2, H14). The merchant confirms what was read before checks run (H5). Untrusted text is wrapped and never obeyed, with red-team tests (H16).
- **Where Chhatri differs.** One model provider, English only and no payout or lending side. Chhatri works in Hindi and English, has built a Gemini, then Sarvam, then templates chain for Ask Chhatri (N2, behind `n2_ask_chhatri`, tested against fakes only), pays the claim and requests the EDI holiday.
- **Check before quoting.** Demo link: mixed. About 100 test functions in 14 files, with no README count.

### 3.5 One-Tap Credit (Team1)

- **What it is.** A decision layer for one moment: whether to show a pre-approved credit offer at the point of payment. It runs 14 ordered gates as pure functions, with affordability first, and explains every decision, including a decision to stay silent.
- **Strong.** The engine reads no clock and no database. The trace includes a counterfactual: what would have to change for the answer to differ. Model copy is rejected if it invents a number. A frequency cap limits offers. An audit trail and four languages.
- **What we took.** Counterfactuals in every explanation (H14). Numbers only from engine facts (H17). No loan offers during distress, and a message cap (H9, X8). The same pure-engine principle as K4 (H10).
- **Where Chhatri differs.** One-Tap Credit covers the offer moment on synthetic data. It has no claims, documents or voice. Chhatri applies the same discipline to a claim and an instalment.
- **Check before quoting.** README states 32 tests. Demo link: mixed.

### 3.6 Resolve OS

- **What it is.** A support desk for Paytm merchant settlement, refund and device problems. It reads Hinglish WhatsApp messages and escalates to people when policy says no.
- **Strong.** "Zero fund rights" for the model: it classifies and proposes, and a deterministic engine enforces every limit. SHA-256 policy tokens are burned on use, so a decision cannot be replayed. An immutable audit schema. A fixture planner when no key is set. Judges can change the data and watch the policy react.
- **What we took.** The principle that code decides money (H10, shared with K4). The provider panel and fallback switch (H7). Counts from events (H8). The what-if panel for judges (H24). A published evaluation (H25).
- **Where Chhatri differs.** A different domain: support operations, with WhatsApp text as the only inbound channel. Chhatri applies the principle to cover, claims and an instalment request.
- **Check before quoting.** README states 39 passing tests, 19 of 19 rubric checks and 40 policy benchmarks. The track is "Autonomous AI Teammates".

### 3.7 FINPATH

- **What it is.** A Flutter app that starts from a life goal and walks through profile, affordability, document review, an application or claim draft, a simulated tracker and human support.
- **Strong.** A deterministic affordability engine. A review dialog before extracted data is used. Consent toggles with an activity log. Scam-message patterns (OTP, advance fees, guarantees, urgency, short links). Five language options with speech input and read-aloud. An honest verification note.
- **What we took.** The review gate and checklist (H5, H15), the scam warning (H19) and the consent activity log (H23).
- **Where Chhatri differs.** FINPATH is general personal finance. Chhatri is built around a small merchant's income and instalment.
- **Check before quoting.** README states 25 Flutter tests and 8 backend smoke checks. Its verification note says live Gemini was not tested because no key was supplied. FINPATH is not FinPath AI.

### 3.8 FinPath AI

- **What it is.** A goal-first platform: a plain-language goal becomes a mission with a five-factor readiness score, next-best-action rules and document OCR with user confirmation.
- **Strong.** The readiness and next-action engines are rules, not a model. Gemini has a keyword fallback. A zero-login `/demo` route lets a judge try it at once. Clear docs.
- **What we took.** A zero-login demo (H6, which N7 delivers). Human confirmation of extracted data (H5, H15). The idea of showing what affects a result and what would improve it (H24).
- **Where Chhatri differs.** The demo is an education-loan journey, and we saw no insurance-claim example. Chhatri's demo is an income claim and an instalment request.
- **Check before quoting.** README states 18 passing tests. Demo link: both OK. FinPath AI is not FINPATH.

### 3.9 ClaimSaathi

- **What it is.** A coverage Q&A on one preloaded health policy. It finds the relevant clauses, checks waiting periods in code and answers with page and clause citations.
- **Strong.** The model never calculates dates or months: Python owns the arithmetic. Every answer cites page and clause. It refuses to answer below a relevance score instead of guessing.
- **What we took.** Nothing yet: we found it on 2 Oct. It shares the principles behind H10 (code owns numbers) and H17 (cite the clause).
- **Where Chhatri differs.** ClaimSaathi covers one policy, with no upload, no claim submission, and no officer or lender side. Chhatri runs the whole claim.
- **Check before quoting.** No README in the repository, one test file, and no public demo address (a free-tier Render config exists).

## 4. Ideas we looked at and did not adopt

| Idea (project) | Why not | What we do instead |
|---|---|---|
| Blockchain registry or signed on-chain claim ledger (Paytm Virasat) | Out of scope for income cover. A database log is enough for tamper evidence | Hash-chained audit log (K7), checked by `GET /api/audit/verify` |
| Multi-agent orchestration (SAHAAY, others) | A model that calls the engine as a tool, or that decides money, breaks ADR 0001 | One deterministic engine. Models read and explain, they never decide |
| XP points, streaks and progress rings (Sahayak) | A claim is not a habit to build, and a merchant in a bad week does not need a game | A plain tracker with one reason per step (H1) |
| Frosted-glass visual style (Vyapaar Saathi) | Not part of our design system, which aims for trustworthy, scannable screens ([design system §1](../03-design/design-system.md)) | The console keeps its plain CSS tokens. The mini-app follows the same tokens, scoped under `.miniapp` |
| Payout "tiers" (Sahayak's three loan sizes) | Our payout is a formula with a cap. Tiers would invite choosing the outcome | One formula, shown with its numbers (H2) |
| A numeric readiness score for the slip (Claim Advocate, FinPath AI, SetuAI) | False precision, and it invites trial and error | A checklist with PASS and WARN lines and no score (N3, H15) |
| Confidence percentages shown to merchants (SetuAI, FinSaathi) | A model's own confidence is not calibrated | The confidence gate stays internal. H25 measures before anyone relies on it |
| Vector search over policy text (Praman, Claim Advocate, ClaimSaathi) | Our wording is 12 clauses. Clause ids are simpler to test | Clause chips C1 to C12, with every number from engine facts (H17) |
| Paid AI services (several) | The project uses free tools only | Gemini free tier, Sarvam credits, templates |

## 5. What this means for Chhatri

1. **Our edge is narrow and specific.** In the repositories we read, we did not find a claim that starts itself. In Chhatri it does, from the merchant's own sales, and the payout is tied to a loan instalment request. We say this carefully: the sales are simulated and the lender is simulated.
2. **We are behind on what a judge can open.** Several projects have a live link and a merchant-facing screen. We have built the mini-app (N1), put the AI paths behind labels (N2 to N4) and built a static copy (N7), all behind flags. None has been run with a key, and the static copy is not deployed.
3. **The closest overlap is Praman.** It is strong in the understand, submit and resolve stages for health claims. Our answer is not to match its breadth. It is to show the full path (check-in, one photo, decision, payout, EDI request) with the sources, counterfactual and labels (H13, H14, H26) that Praman, One-Tap Credit and Rakshak showed us.

## Open questions

1. Should we re-scan on the morning of 3 Oct? Praman changed during 2 Oct. Owner: Omkar Kadam.
2. Re-check the three "mixed" demo links before any of them is quoted. Owner: Omkar Kadam.
3. If results are published for any edition, add them here and in the landscape. Owner: Omkar Kadam.

## Changelog

- 2026-10-03 · v1.1 · Chhatri's own status updated (features built behind flags); the scan is unchanged
- 2026-10-02 · v1 · first version, from the 2 Oct scan: 28 projects in one table, notes on the nine closest, ideas not adopted. Includes the three repositories added after the first pass (JeevanFlow, ClaimSaathi, GrowSAATHI) and Praman's 2 Oct update
