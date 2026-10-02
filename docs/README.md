# Chhatri documentation

| | |
|---|---|
| Status | Draft v1.2 · 2 Oct 2026 |
| Owner | Omkar Kadam |
| Audience | Judges, teammates, engineers, partners |
| Related | [Executive summary](00-executive-summary.md) · [Facts and sources](01-strategy/facts-and-sources.md) · [SPEC.md](SPEC.md) · [Build plan](06-delivery/build-plan.md) |

## TL;DR

- **55 new docs** across strategy, product, design, engineering, business and delivery are indexed below. Five existing docs (SPEC, ARCHITECTURE, DEMO, INTEGRATIONS, SECURITY) remain valid and are referenced.
- **Reading paths** for judges (10 minutes or full), teammates (build plan, specs, implementation guide) and engineers (architecture, ADRs).
- **Every doc** has a header table, TL;DR, numbered sections, open questions and a changelog. External facts cite `facts-and-sources.md` (A1–A25). Code claims include file paths.
- **Status words** are BUILT (in the code and tested), PLANNED (not written yet, with its build wave) and ROADMAP (after the hackathon). **Integration modes** are LIVE, SIMULATED and FALLBACK. **Canonical IDs** are K1–K8 (keep), N1–N8 (new), X1–X8 (fixes), H1–H26 (ideas from other teams), C1–C12 (policy clauses), J1–J10 (journeys), PS-1 to PS-14 and IR-1 to IR-7 (requirements).
- **Build order:** everything not yet built is P0. It is built in six waves behind feature flags, and a feature that is not finished is hidden, never shown half-working ([build plan](06-delivery/build-plan.md)).
- **Conventions:** no personal emails or phone numbers; Indian number format (₹1,380; 1.57 crore); Hindi in Devanagari with English beside; professional tone, short sentences, no hype.

**User manual:** [user-manual.pdf](user-manual.pdf), a plain-English guide for a first-time reader with a screenshot of every screen (source: [user-manual/user-manual.html](user-manual/user-manual.html)).

## Reading paths by audience

**Judge (10 min):** [Executive summary](00-executive-summary.md) → [Problem statement analysis](01-strategy/problem-statement-analysis.md) → [User journeys](02-product/user-journeys.md) → [Demo runbook](06-delivery/demo-runbook.md) → [Pitch and Q&A](06-delivery/pitch-and-judge-qa.md).

**Judge (full):** the 10-minute path, then the [Requirements traceability matrix](01-strategy/requirements-traceability-matrix.md) → [Competitive landscape](01-strategy/competitive-landscape.md) → [Rival teardown appendix](01-strategy/rival-teardown-appendix.md) → [Policy wording](02-product/policy-wording-and-cis.md) → [AI evaluation plan](04-engineering/ai-evaluation-plan.md) → [Regulatory and compliance](05-business/regulatory-and-compliance.md).

**Teammate (2–3 Oct build):** [Build plan](06-delivery/build-plan.md) → [PRD](02-product/prd.md) → [Feature specs](02-product/feature-specs/) → [Implementation guide](04-engineering/implementation-guide.md) → [Data model and API](04-engineering/data-model-and-api.md) → [Testing](04-engineering/testing-and-quality-strategy.md) → [On-site checklist](06-delivery/on-site-checklist.md).

**Engineer new to code:** [System architecture](04-engineering/system-architecture.md) → [ADRs](04-engineering/adr/README.md) → [SPEC.md](SPEC.md) → [ARCHITECTURE.md](ARCHITECTURE.md) → [Data model](04-engineering/data-model-and-api.md) → [Implementation guide](04-engineering/implementation-guide.md).

## Documentation table

| Path | Purpose | Owner | Status |
|---|---|---|---|
| **Overview** | | | |
| [00-executive-summary.md](00-executive-summary.md) | One-page story for judges and teammates | Omkar | Draft |
| **Core strategy (01-strategy/)** | | | |
| [01-strategy/facts-and-sources.md](01-strategy/facts-and-sources.md) | A1–A25 verified facts, regulatory hedges, code facts | Both | Draft |
| [01-strategy/problem-statement-analysis.md](01-strategy/problem-statement-analysis.md) | Track statement, requirements, and the health-claims example walked on hospital cash | Omkar | Draft |
| [01-strategy/requirements-traceability-matrix.md](01-strategy/requirements-traceability-matrix.md) | 14 track requirements and 7 implicit ones traced to features, status and wave, demo moments and tests | Omkar | Draft |
| [01-strategy/current-state-audit.md](01-strategy/current-state-audit.md) | Strengths, fixes (X1–X8) | Omkar | Draft |
| [01-strategy/competitive-landscape.md](01-strategy/competitive-landscape.md) | Rivals, ideas adopted (H1–H26) with credits | Omkar | Draft |
| [01-strategy/rival-teardown-appendix.md](01-strategy/rival-teardown-appendix.md) | One row per rival project from the 2 Oct scan, notes on the nine closest, ideas not adopted | Omkar | Draft |
| [01-strategy/hackathon-playbook.md](01-strategy/hackathon-playbook.md) | Final-day format, roles, contingencies | Omkar | Draft |
| **Product (02-product/)** | | | |
| [02-product/vision-and-positioning.md](02-product/vision-and-positioning.md) | Vision, principles, roadmap | Omkar | Draft |
| [02-product/personas-and-jtbd.md](02-product/personas-and-jtbd.md) | Anil, Ramesh, Priya, Rajesh, Amit | Omkar | Draft |
| [02-product/metrics-and-impact.md](02-product/metrics-and-impact.md) | North star, input metrics, AI evals | Omkar | Draft |
| [02-product/user-journeys.md](02-product/user-journeys.md) | J1–J10 end to end | Omkar | Draft |
| [02-product/prd.md](02-product/prd.md) | Scope with build waves, FR IDs, acceptance criteria, NFRs | Omkar | Draft |
| [02-product/policy-wording-and-cis.md](02-product/policy-wording-and-cis.md) | C1–C12 wording, customer info sheet | Omkar | Draft |
| **Feature specs (02-product/feature-specs/)** | | | |
| [02-product/feature-specs/fs-01-area-auto-claim.md](02-product/feature-specs/fs-01-area-auto-claim.md) | K1 (X2) | Omkar | Draft |
| [02-product/feature-specs/fs-02-hospital-cash-claim.md](02-product/feature-specs/fs-02-hospital-cash-claim.md) | K2 + N3 + H5 + H15 | Omkar | Draft |
| [02-product/feature-specs/fs-03-edi-holiday.md](02-product/feature-specs/fs-03-edi-holiday.md) | K3 + X4 + X8 | Omkar | Draft |
| [02-product/feature-specs/fs-04-merchant-mini-app.md](02-product/feature-specs/fs-04-merchant-mini-app.md) | N1 + H1 to H3 + H20 + H21 | Omkar | Draft |
| [02-product/feature-specs/fs-05-ask-chhatri.md](02-product/feature-specs/fs-05-ask-chhatri.md) | N2 + N4 + H16 to H19 + H26 | Omkar | Draft |
| [02-product/feature-specs/fs-06-explanations-disputes-and-grievance.md](02-product/feature-specs/fs-06-explanations-disputes-and-grievance.md) | K5 + N5 + H22 | Omkar | Draft |
| [02-product/feature-specs/fs-07-cover-purchase-and-consent.md](02-product/feature-specs/fs-07-cover-purchase-and-consent.md) | K6 + N6 + H23 (X3) | Omkar | Draft |
| [02-product/feature-specs/fs-08-claims-officer-console.md](02-product/feature-specs/fs-08-claims-officer-console.md) | K8 + X6 + H8 + H24 | Omkar | Draft |
| [02-product/feature-specs/fs-09-policy-engine-and-audit.md](02-product/feature-specs/fs-09-policy-engine-and-audit.md) | K4 + K7 + H13 + H14 | Omkar | Draft |
| **Design (03-design/)** | | | |
| [03-design/design-system.md](03-design/design-system.md) | Tokens, Devanagari type, components, a11y | Omkar | Draft |
| [03-design/screens-and-flows.md](03-design/screens-and-flows.md) | Console and mini-app layouts, flows | Omkar | Draft |
| [03-design/conversation-design.md](03-design/conversation-design.md) | Voice, message catalogue, intents, Marathi | Omkar | Draft |
| [03-design/copy-deck.md](03-design/copy-deck.md) | Every new merchant-facing string, proposed, with keys and English, Hindi and Marathi drafts | Omkar | Draft |
| **Engineering (04-engineering/)** | | | |
| [04-engineering/system-architecture.md](04-engineering/system-architecture.md) | Containers, flows, live/simulated switching | Ujjwal | Draft |
| [04-engineering/implementation-guide.md](04-engineering/implementation-guide.md) | How to build the P0 work in waves: the feature-flag mechanism, set-up and the console and mini-app boundary | Ujjwal | Draft |
| [04-engineering/data-model-and-api.md](04-engineering/data-model-and-api.md) | Domain, storage, existing and planned endpoints | Ujjwal | Draft |
| [04-engineering/ai-architecture-and-guardrails.md](04-engineering/ai-architecture-and-guardrails.md) | Provider chains, evals, guardrails | Ujjwal | Draft |
| [04-engineering/ai-evaluation-plan.md](04-engineering/ai-evaluation-plan.md) | H25: how AI quality is measured. PLANNED for Wave 3, nothing measured yet | Ujjwal | Draft |
| [04-engineering/ml-model-card.md](04-engineering/ml-model-card.md) | LightGBM model, backtest, calibration | Ujjwal | Draft |
| [04-engineering/free-tier-stack-and-setup.md](04-engineering/free-tier-stack-and-setup.md) | Keys, env vars, quotas, static deploy | Ujjwal | Draft |
| [04-engineering/testing-and-quality-strategy.md](04-engineering/testing-and-quality-strategy.md) | Suites, gates, new tests (X1–X8), evals | Ujjwal | Draft |
| **ADRs (04-engineering/adr/)** | | | |
| [04-engineering/adr/README.md](04-engineering/adr/README.md) | ADR index | Ujjwal | Draft |
| [04-engineering/adr/0001-policy-engine-is-the-only-payout-authority.md](04-engineering/adr/0001-policy-engine-is-the-only-payout-authority.md) | K4 | Ujjwal | Draft |
| [04-engineering/adr/0002-area-sales-index-trigger.md](04-engineering/adr/0002-area-sales-index-trigger.md) | K1 | Ujjwal | Draft |
| [04-engineering/adr/0003-free-ai-provider-chain.md](04-engineering/adr/0003-free-ai-provider-chain.md) | N2–N4 | Ujjwal | Draft |
| [04-engineering/adr/0004-live-simulated-fallback-labels.md](04-engineering/adr/0004-live-simulated-fallback-labels.md) | Status labels | Ujjwal | Draft |
| [04-engineering/adr/0005-mini-app-inside-the-console.md](04-engineering/adr/0005-mini-app-inside-the-console.md) | N1 | Omkar | Draft |
| [04-engineering/adr/0006-edi-holiday-is-the-lenders-decision.md](04-engineering/adr/0006-edi-holiday-is-the-lenders-decision.md) | K3 | Omkar | Draft |
| [04-engineering/adr/0007-hospital-cash-framing.md](04-engineering/adr/0007-hospital-cash-framing.md) | K2 | Omkar | Draft |
| [04-engineering/adr/0008-in-process-workflows-on-stage.md](04-engineering/adr/0008-in-process-workflows-on-stage.md) | In-process runner, X5 | Ujjwal | Draft |
| [04-engineering/adr/0009-synthetic-data-only-to-free-tier-ai.md](04-engineering/adr/0009-synthetic-data-only-to-free-tier-ai.md) | Data privacy, free-tier AI | Ujjwal | Draft |
| **Business (05-business/)** | | | |
| [05-business/business-model-and-unit-economics.md](05-business/business-model-and-unit-economics.md) | Who pays, pricing, unit economics | Omkar | Draft |
| [05-business/go-to-market-and-pilot-plan.md](05-business/go-to-market-and-pilot-plan.md) | Pilot design, channels, timeline, asks | Omkar | Draft |
| [05-business/regulatory-and-compliance.md](05-business/regulatory-and-compliance.md) | Insurance, lending, grievance, DPDP, FREE-AI | Omkar | Draft |
| **Delivery (06-delivery/)** | | | |
| [06-delivery/build-plan.md](06-delivery/build-plan.md) | Six waves, tasks, owners, flags, checkpoints, hide order | Both | Draft |
| [06-delivery/risk-register.md](06-delivery/risk-register.md) | Risks, likelihood, impact, mitigation | Both | Draft |
| [06-delivery/demo-runbook.md](06-delivery/demo-runbook.md) | 3-min and 7-min cuts with fallbacks | Omkar | Draft |
| [06-delivery/pitch-and-judge-qa.md](06-delivery/pitch-and-judge-qa.md) | Pitch cuts, key lines, judge questions and answers | Omkar | Draft |
| [06-delivery/final-deck-and-video-script.md](06-delivery/final-deck-and-video-script.md) | Final deck, slide by slide, and the backup video script | Omkar | Draft |
| [06-delivery/on-site-checklist.md](06-delivery/on-site-checklist.md) | Checks for the final day: on arrival, T−60 and T−30 | Both | Draft |
| **Core docs** | | | |
| [glossary.md](glossary.md) | Terms, IDs, Hindi words | Both | Draft |

## How new docs relate to existing docs

- **SPEC.md** (contract): never silently contradicted. Changes to copy, API or flows are tracked in feature specs with change-request notes.
- **ARCHITECTURE.md, DEMO.md, INTEGRATIONS.md, SECURITY.md**: remain valid, and may be corrected where they are wrong or stale. New integrations and guards are documented in AI architecture and feature specs. `scripts/tests/test_docs.py` checks that DEMO.md quotes the message catalogue and the golden strings exactly, that every `make` target named in the README and the original docs exists, and that the paths they list exist, so keep those strings when you edit.
- **Screenshots**: wireframes and console layouts in `assets/screens/` referenced from design and feature specs. Status words apply to screenshots too (BUILT, PLANNED).

## Legends

**Status:** BUILT (in the code and tested at commit 86575ea) · PLANNED (not written yet, with its build wave, 0 to 5) · ROADMAP (after the hackathon).

**Integration modes:** LIVE (a real service answered) · SIMULATED (a labelled simulator) · FALLBACK (a backup provider answered; arrives with X6 in Wave 2).

**IDs:** K1–K8 keep features · N1–N8 new features · X1–X8 fixes · H1–H26 ideas from other teams (credits in the competitive landscape) · C1–C12 policy clauses · J1–J10 journeys · FR-… functional requirements in the PRD · PS-1 to PS-14 track requirements · IR-1 to IR-7 implicit requirements · A1–A25 external facts · ADR architecture decisions.

**Demo numbers (quote exactly):** Anil ₹1,380 at 17:04; Z7 total ₹58,900. Hospital-cash ₹1,500. Measured on 3 Oct 2026: backend 3,221 fast and 63 slow tests pass (98.85% coverage); frontend 1,340 unit tests pass; infra 164; demo-check 70 of 70. Replay speed 6 simulated minutes per real second.

**Conventions:** No personal emails or phone numbers. Indian format (₹1,380; 1.57 crore). Hindi in Devanagari with English (for example "छत्री (Chhatri)"). Professional, short sentences, active voice. Links are relative. Facts cited as (A3), code as `path/to/file.py`. Every doc has a header table, TL;DR, numbered sections, open questions and changelog.

## Open questions

1. How will we batch updates to SPEC.md, DEMO.md on the final day? Owner: Both.
2. What is the threshold for a change request vs discovery during development? Owner: Omkar.
3. Who updates the traceability matrix, the competitive landscape and the build plan's status line at each wave checkpoint? Owner: Both.

## Changelog

- 2026-10-02 · v1.2 · indexed the seven new docs (implementation guide, AI evaluation plan, copy deck, on-site checklist, final deck and video script, rival teardown appendix, requirements traceability matrix); doc count now 55, one row per indexed file; ID legend now H1–H26, PS-1 to PS-14 and IR-1 to IR-7; status legend uses BUILT and PLANNED, with LIVE, SIMULATED and FALLBACK as integration modes; reading paths added for a full judge read and for the implementation guide; feature-spec coverage updated; notes on what the docs test checks
- 2026-10-02 · v1.1 · fact-check pass: added full file paths to all docs in the table with working relative links; added 00-executive-summary.md.
- 2026-10-02 · v1 · first draft.
