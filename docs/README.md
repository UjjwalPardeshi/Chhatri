# Chhatri documentation

| | |
|---|---|
| Status | Draft v1 · 2 Oct 2026 |
| Owner | Omkar Kadam |
| Audience | Judges, teammates, engineers, partners |
| Related | [Executive summary](00-executive-summary.md) · [Facts and sources](01-strategy/facts-and-sources.md) · [SPEC.md](SPEC.md) |

## TL;DR

- **47 new docs** across strategy, product, design, engineering, business and delivery; five existing docs (SPEC, ARCHITECTURE, DEMO, INTEGRATIONS, SECURITY) remain valid and are referenced.
- **Reading paths** for judges (10 min or full), teammates (build plan + specs), engineers (architecture + ADRs).
- **Every doc** has a header table, TL;DR, numbered sections, open questions, and a changelog. External facts cite `facts-and-sources.md` (A1–A25). Code claims include file paths.
- **Status labels** (LIVE, SIMULATED, FALLBACK, PLANNED, ROADMAP) and **canonical IDs** (K1–K8 keep, N1–N8 new, X1–X8 fixes, H1–H12 ideas, C1–C12 policy clauses, J1–J10 journeys).
- **Conventions:** no personal emails or phone numbers; Indian number format (₹1,380; 1.57 crore); Hindi in Devanagari with English beside; professional tone, short sentences, no hype.

## Reading paths by audience

**Judge (10 min):** [Executive summary](00-executive-summary.md) → [Problem statement analysis](01-strategy/problem-statement-analysis.md) → [User journeys](02-product/user-journeys.md) → [Demo runbook](06-delivery/demo-runbook.md) → [Pitch and Q&A](06-delivery/pitch-and-judge-qa.md).

**Teammate (2–3 Oct build):** [Build plan](06-delivery/build-plan.md) → [PRD](02-product/prd.md) → [Feature specs](02-product/feature-specs/) → [Data model and API](04-engineering/data-model-and-api.md) → [Testing](04-engineering/testing-and-quality-strategy.md).

**Engineer new to code:** [System architecture](04-engineering/system-architecture.md) → [ADRs](04-engineering/adr/README.md) → [SPEC.md](SPEC.md) → [ARCHITECTURE.md](ARCHITECTURE.md) → [Data model](04-engineering/data-model-and-api.md).

## Documentation table

| Path | Purpose | Owner | Status |
|---|---|---|---|
| **Overview** | | | |
| [00-executive-summary.md](00-executive-summary.md) | One-page story for judges and teammates | Omkar | Draft |
| **Core strategy (01-strategy/)** | | | |
| [01-strategy/facts-and-sources.md](01-strategy/facts-and-sources.md) | A1–A25 verified facts, regulatory hedges, code facts | Both | LIVE |
| [01-strategy/problem-statement-analysis.md](01-strategy/problem-statement-analysis.md) | Track statement → requirements → features | Omkar | Draft |
| [01-strategy/current-state-audit.md](01-strategy/current-state-audit.md) | Strengths, fixes (X1–X8) | Omkar | Draft |
| [01-strategy/competitive-landscape.md](01-strategy/competitive-landscape.md) | Rivals, ideas adopted (H1–H12) | Omkar | Draft |
| [01-strategy/hackathon-playbook.md](01-strategy/hackathon-playbook.md) | Final-day format, roles, contingencies | Omkar | Draft |
| **Product (02-product/)** | | | |
| [02-product/vision-and-positioning.md](02-product/vision-and-positioning.md) | Vision, principles, roadmap | Omkar | Draft |
| [02-product/personas-and-jtbd.md](02-product/personas-and-jtbd.md) | Anil, Ramesh, Priya, Rajesh, Amit | Omkar | Draft |
| [02-product/metrics-and-impact.md](02-product/metrics-and-impact.md) | North star, input metrics, AI evals | Omkar | Draft |
| [02-product/user-journeys.md](02-product/user-journeys.md) | J1–J10 end to end | Omkar | Draft |
| [02-product/prd.md](02-product/prd.md) | Scope, FR IDs, acceptance criteria, NFRs | Omkar | Draft |
| [02-product/policy-wording-and-cis.md](02-product/policy-wording-and-cis.md) | C1–C12 wording, customer info sheet | Omkar | Draft |
| **Feature specs (02-product/feature-specs/)** | | | |
| [02-product/feature-specs/fs-01-area-auto-claim.md](02-product/feature-specs/fs-01-area-auto-claim.md) | K1 | Omkar | Draft |
| [02-product/feature-specs/fs-02-hospital-cash-claim.md](02-product/feature-specs/fs-02-hospital-cash-claim.md) | K2 + N3 + H5 | Omkar | Draft |
| [02-product/feature-specs/fs-03-edi-holiday.md](02-product/feature-specs/fs-03-edi-holiday.md) | K3 + X4 + X8 | Omkar | Draft |
| [02-product/feature-specs/fs-04-merchant-mini-app.md](02-product/feature-specs/fs-04-merchant-mini-app.md) | N1 + H1 + H2 + H3 | Omkar | Draft |
| [02-product/feature-specs/fs-05-ask-chhatri.md](02-product/feature-specs/fs-05-ask-chhatri.md) | N2 + N4 | Omkar | Draft |
| [02-product/feature-specs/fs-06-explanations-disputes-and-grievance.md](02-product/feature-specs/fs-06-explanations-disputes-and-grievance.md) | K5 + N5 + H2 | Omkar | Draft |
| [02-product/feature-specs/fs-07-cover-purchase-and-consent.md](02-product/feature-specs/fs-07-cover-purchase-and-consent.md) | K6 + N6 | Omkar | Draft |
| [02-product/feature-specs/fs-08-claims-officer-console.md](02-product/feature-specs/fs-08-claims-officer-console.md) | K8 + H7 + H8 | Omkar | Draft |
| [02-product/feature-specs/fs-09-policy-engine-and-audit.md](02-product/feature-specs/fs-09-policy-engine-and-audit.md) | K4 + K7 | Omkar | Draft |
| **Design (03-design/)** | | | |
| [03-design/design-system.md](03-design/design-system.md) | Tokens, Devanagari type, components, a11y | Omkar | Draft |
| [03-design/screens-and-flows.md](03-design/screens-and-flows.md) | Console and mini-app layouts, flows | Omkar | Draft |
| [03-design/conversation-design.md](03-design/conversation-design.md) | Voice, message catalogue, intents, Marathi | Omkar | Draft |
| **Engineering (04-engineering/)** | | | |
| [04-engineering/system-architecture.md](04-engineering/system-architecture.md) | Containers, flows, live/simulated switching | Ujjwal | Draft |
| [04-engineering/data-model-and-api.md](04-engineering/data-model-and-api.md) | Domain, storage, existing + new endpoints | Ujjwal | Draft |
| [04-engineering/ai-architecture-and-guardrails.md](04-engineering/ai-architecture-and-guardrails.md) | Provider chains, evals, guardrails | Ujjwal | Draft |
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
| [06-delivery/build-plan.md](06-delivery/build-plan.md) | Hour-by-hour plan, task owners, dependencies | Both | Draft |
| [06-delivery/risk-register.md](06-delivery/risk-register.md) | Risks, likelihood, impact, mitigation | Both | Draft |
| [06-delivery/demo-runbook.md](06-delivery/demo-runbook.md) | 3-min and 7-min cuts with fallbacks | Omkar | Draft |
| [06-delivery/pitch-and-judge-qa.md](06-delivery/pitch-and-judge-qa.md) | Pitch outlines, 45+ Q&A | Omkar | Draft |
| **Core docs** | | | |
| [glossary.md](glossary.md) | Terms, IDs, Hindi words | Both | Draft |

## How new docs relate to existing docs

- **SPEC.md** (contract): never silently contradicted. Changes to copy, API or flows are tracked in feature specs with change-request notes.
- **ARCHITECTURE.md, DEMO.md, INTEGRATIONS.md, SECURITY.md**: remain valid. New integrations and guards are documented in AI architecture and feature specs; any change to the live record is a change request to the existing doc.
- **Screenshots**: wireframes and console layouts in `assets/screens/` referenced from design and feature specs. Status labels apply to screenshots too (PLANNED, LIVE, etc.).

## Legends

**Status:** LIVE (works today, tested) · SIMULATED (labelled simulator) · FALLBACK (degrades gracefully) · PLANNED (2–3 Oct build) · ROADMAP (post-hackathon).

**IDs:** K1–K8 keep features · N1–N8 new features · X1–X8 fixes · H1–H12 ideas from rivals · C1–C12 policy clauses · J1–J10 journeys · FR, PS feature reqs / problem statements · A1–A25 external facts · ADR architecture decisions.

**Demo numbers (quote exactly):** Anil ₹1,380 at 17:04; Z7 total ₹58,900. Hospital-cash ₹1,500. Backend 1,747 tests pass, 99.7% coverage; frontend 262/264. Replay speed 6 simulated min per real sec.

**Conventions:** No personal emails or phone numbers. Indian format (₹1,380; 1.57 crore). Hindi in Devanagari with English (e.g. "छत्री (Chhatri)"). Professional, short sentences, active voice. Links are relative. Facts cited as (A3), code as `path/to/file.py`. Every doc has a header table, TL;DR, numbered sections, open questions and changelog.

## Open questions

1. How will we batch updates to SPEC.md, DEMO.md on the final day? Owner: Both.
2. What is the threshold for a change request vs discovery during development? Owner: Omkar.
3. Do we have the eval set ready for "honest wording" and "grounding" tests? Owner: Ujjwal.

## Changelog

- 2026-10-02 · v1.1 · fact-check pass: added full file paths to all docs in the table with working relative links; added 00-executive-summary.md.
- 2026-10-02 · v1 · first draft.
