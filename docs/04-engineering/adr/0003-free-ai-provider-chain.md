# 0003: Free AI provider chain

| | |
|---|---|
| Status | Accepted as a decision, 2 Oct 2026. Implementation status: BUILT. The Sarvam and Gemini links, the FALLBACK label, per-component switches, the forced-fallback switch and the free-tier gate exist (Wave 2, behind flags); Gemini and Sarvam were tested against fakes only. Tesseract is not built |
| Owner | Ujjwal Pardeshi |
| Date | 2026-10-02 |
| Related | [SPEC §0.1, §14](../../SPEC.md) · [AI architecture and guardrails §3](../ai-architecture-and-guardrails.md) · [Free-tier stack and setup](../free-tier-stack-and-setup.md) · [ADR 0001](0001-policy-engine-is-the-only-payout-authority.md) · [ADR 0004](0004-live-simulated-fallback-labels.md) · [ADR 0009](0009-synthetic-data-only-to-free-tier-ai.md) · [Ask Chhatri (fs-05) §10](../../02-product/feature-specs/fs-05-ask-chhatri.md) · [Hospital-cash claim (fs-02) §7.2](../../02-product/feature-specs/fs-02-hospital-cash-claim.md) · [Facts and sources (A17, A19)](../../01-strategy/facts-and-sources.md) |

## TL;DR

Every AI need gets an ordered chain of free-tier providers that ends in something deterministic. Gemini comes first where its adapter exists, then Sarvam, then a catalogue template, the simulated reader or a person, depending on the need. A link is in a chain only when fully configured. Each result says which link answered and why (mode, provider, model, fallback reason). No document names a Gemini model or a quota, because both change: the model id is set in an environment variable and chosen from the current free tier in Google AI Studio on the day. Today only the Sarvam links and the simulators exist. The Gemini adapters, the labels and the switches are planned for Wave 2.

## Context

**What exists (BUILT, checked against commit 86575ea on 2 Oct 2026).** Sarvam adapters for chat (default model `sarvam-105b`, setting `SARVAM_CHAT_MODEL`), document reading, speech to text (`saaras:v3`) and text to speech (`bulbul:v3`). The registry builds live adapters when `SARVAM_API_KEY` is set and offline simulators otherwise, and `GET /api/integrations` reports LIVE or SIMULATED for 15 named components. Chat is used for one thing: choosing an intent for UNKNOWN text, from the nine intent values. The rules answer everything else.

**What does not exist.** Gemini adapters, a FALLBACK mode, per-component toggles, a forced-fallback switch, a free-tier data gate, Tesseract and browser speech recognition. This ADR describes the design for them. It does not say they run.

**Constraints.** The project uses free tools only. Free tiers have quotas that are not stable and can fail during a demo. The team holds Sarvam free credits. A Google AI Studio key is a Wave 0 task. Content sent to a free tier may be used by the provider (facts A19), so only synthetic data is sent ([ADR 0009](0009-synthetic-data-only-to-free-tier-ai.md)).

**Why a chain.** One free tier is one point of failure. A chain keeps each flow working when a provider is slow, out of quota or down, and the label keeps the demo honest about which link answered. The design puts Gemini first for grounded text and vision on the expectation that it writes Hindi and reads photos well. That expectation is to be measured in the harness (H25), not assumed. Sarvam is built for Indian languages and speech and is already integrated.

## Decision

**1. One chain per need.** Chains are fixed in order and end deterministically.

| Need | Chain | BUILT at commit 86575ea | Added in Wave 2 (BUILT, behind flags) |
|---|---|---|---|
| Ask Chhatri answer (N2) | Rules for known intents, then Gemini chat, then Sarvam chat, then a catalogue template | Rules, templates and the Sarvam chat adapter | Gemini chat adapter, the Ask service and its guard (Wave 2) |
| Intent for UNKNOWN text | Sarvam chat (intent value only, 500 characters at most), then the rules' UNKNOWN | BUILT | Replaced by the Ask path when N2 is on: the model no longer chooses intents |
| Slip reading (N3) | Gemini vision, then Sarvam Vision (document intelligence), then REFERRED. The simulated reader when the chain has no live link, the data gate is closed or fallback is forced | Sarvam adapter, simulated reader, REFERRED on a read failure | Gemini vision adapter, the pre-check, labels (Wave 2) |
| Speech to text (N4) | Sarvam, then browser recognition, then typed text with confirmation chips | Sarvam adapter, simulator | Browser recognition, chips (Wave 2) |
| Text to speech (N4) | Sarvam (demo merchants only today), then browser `speechSynthesis`, then text | BUILT | `POST /api/voice/tts` (Wave 2) |

Tesseract is a PLANNED later link for slips, after Sarvam and before REFERRED. It is not in the Wave 2 chain and its output would never be given to a model. Workflows and memory are not AI chains: see [ADR 0008](0008-in-process-workflows-on-stage.md) and AI architecture §1.

**2. Rules for every chain.**

1. A link is in the chain only when fully configured: Sarvam needs `SARVAM_API_KEY`, Gemini needs `GOOGLE_API_KEY` and a model id in `GEMINI_MODEL` (name proposed). A Gemini key without a model id leaves Gemini out and the provider panel says "key set, model not set".
2. Failure falls through to the next link. The BUILT retry plumbing applies: retries only on HTTP 429 and 5xx, at most 3 attempts in all with waits of 0.5 s then 1 s, no retry on a timeout, safe error messages. The default timeout is 10 s and the Sarvam document bound is 60 s. On interactive paths each link gets one attempt, with budgets set in the Wave 2 rehearsal so a chain fits its target (Ask 5 s for at least 95 % of rehearsal questions, slip read 10 s for at least 90 %, both targets and unmeasured).
3. Every AI-backed result carries `mode`, `provider`, `model`, `fallback_reason` and `attempts` ([fs-05 §10](../../02-product/feature-specs/fs-05-ask-chhatri.md)). SIMULATED means no live path was configured or allowed. FALLBACK means a configured link failed or was blocked and a later link answered. LIVE means the chain worked as designed.
4. The model id comes from the environment and is echoed in the label. Screens never hard-code a model name. Documents name no Gemini model and no quota, because both change. The Sarvam defaults quoted here are read from the code.
5. The free-tier data gate of [ADR 0009](0009-synthetic-data-only-to-free-tier-ai.md) is asked before any free-tier link is called.
6. No provider output sets money ([ADR 0001](0001-policy-engine-is-the-only-payout-authority.md)). Text goes through the guard and fields through schema validation, whatever the provider.
7. Gemini adapters follow the Sarvam pattern: `integrations/gemini_chat.py` implements the BUILT `ChatModel` protocol and `integrations/gemini_vision.py` implements the BUILT `SlipReader` protocol, both over the shared retry module. The registry gains the status names `gemini_chat` and `gemini_vision` (proposed), which changes the fixed list of 15 names in SPEC §19.2. X6 adds the per-component toggles and `POST /api/integrations/{component}/fallback`.

**3. Starting the chain.** At startup `build_integrations()` reads the settings. A component is LIVE when its live adapter is in use and SIMULATED otherwise. FALLBACK appears per result, not per component, because it describes what happened to one request.

## Alternatives considered

1. **Gemini first, Sarvam second, deterministic last (chosen).** Two providers give resilience and let each be switched off to protect its quota. The cost is an adapter, a chain and labels to build and test, and a Google AI Studio key.
2. **Sarvam only (the BUILT state).** Simplest, and it already works. One free tier is a single point of failure, and a second provider cannot be compared against it. Kept as the second link and as the state when no Gemini key is set.
3. **Local models only.** No external dependency and no quota. The team has not evaluated local model quality or latency for Hindi grounding or slip reading, and evaluating them would cost time the waves do not have. Not chosen for Wave 2. A pilot with real data needs a processor decision under ADR 0009 and this stays open.
4. **Paid APIs.** Rejected by the project rule that only free tools are used.
5. **Simulators only.** Fully deterministic and always available, but nothing live to evaluate or show. Kept as the last link and for tests, never presented as live.

## Consequences

**Positive**

- Zero cost for the prototype.
- A failing link degrades one flow, not the product, and the label says what happened.
- Two providers can be compared on the same sets in the evaluation harness (H25).
- Adapters reuse existing plumbing, so the new code is small and testable with fakes.

**Negative**

- Free quotas are not stable. They can only be known from AI Studio and the Sarvam dashboard on the day.
- More code and tests: two adapters, a chain with attempts, labels and switches.
- Quality is unmeasured. Free models can be wrong. The guard, schemas, the merchant's confirmation and the engine's checks carry the safety, and H25 measures the rest.
- A failed link spends its time budget before the next one starts, so budgets matter.

**Risks and mitigations**

- Quota runs out on stage: per-component toggles and the forced-fallback switch (X6), and a rehearsal that records real call counts.
- Key exposure: keys are environment-only, `.env` is not committed, and keys are rotated after the event.
- A model is renamed or retired: the id is an environment variable and is echoed in every label.
- The two providers behave differently on the same prompt: validation and the guard are provider-independent, and the evaluation runs each provider separately.
- Provider terms allow reuse of free-tier content: only synthetic data is sent, and the data gate enforces it ([ADR 0009](0009-synthetic-data-only-to-free-tier-ai.md)).

## How we will know it was right

1. A chain test with fakes shows the fixed order, skipped unconfigured links, and the right label for every failure reason.
2. `GET /api/integrations` and the provider panel show per-component status, including "key set, model not set".
3. The Wave 2 rehearsal measures latency against the two targets and records fallback counts.
4. A forced-fallback drill completes every flow with the label SIMULATED and reason `FORCED`.
5. The first harness run (Wave 3) measures each provider separately and shows the numbers on `/evals`. Until then nothing about provider quality is claimed.

## Follow-ups

- **Wave 0, Ujjwal Pardeshi.** Create a Google AI Studio key. Read the current free-tier model list and limits in AI Studio, pick one model that accepts text and images (or two), confirm it returns JSON that matches a schema, and record the choice in the rehearsal notes, not in documents.
- **Wave 2, Ujjwal Pardeshi.** Gemini chat and vision adapters, the chains with attempts and labels, the new status names, per-component toggles, forced fallback and the data gate (tasks N2.1, N2.10, N3.2, N3.3). Tests with fakes for every failure reason.
- **Wave 2, Omkar Kadam.** Provider panel and label display (X6, H26).
- **Wave 2 rehearsal.** Set per-link budgets, decide the stage toggles in advance, and count real calls against the quota shown in the consoles.
- **Wave 3.** Run the harness per provider and add the measured results to this ADR's changelog.

## Open questions

1. Can the Gemini or Sarvam quotas be raised for a pilot, and at what cost? Owner: Ujjwal Pardeshi.
2. For production, should the first link be Gemini, Sarvam, or a model run inside the insurer's infrastructure? This depends on ADR 0009 and the processor decision. Owner: Ujjwal Pardeshi.
3. Should Gemini and Sarvam chat share one system prompt and one guard? The default is yes. A provider-specific prompt is allowed only if the evaluation shows a need. Owner: Ujjwal Pardeshi.

## Changelog

- 2026-10-02 · status synced with the working tree at the end of the build: the PLANNED parts named here are BUILT behind their flags
- 2026-10-02 · v3 · aligned with the code and the Wave 2 specs: decision Accepted while implementation is PLANNED, stated explicitly; one chain per need with BUILT and PLANNED columns; the intent call is Sarvam for UNKNOWN text only and is replaced by the Ask path; Gemini adapters follow the Sarvam pattern with the model id in an environment variable and no model name or quota in documents; Tesseract and browser speech recognition are planned and not in the Wave 2 chain; retry facts corrected (waits of 0.5 s then 1 s); removed the invented adapter size, "judges expect two providers" note, free-tier limits for browser speech, the "marked LIVE if reachable" rule, the status-flapping mitigation and the time-of-day milestones
- 2026-10-02 · v2 · final consistency pass against the code: no changes needed; ADR correctly describes the provider chain (Gemini PLANNED, Sarvam TODAY) and synthetic-only rule for free tiers.
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned: restored Gemini free tier as PLANNED first provider (Oct 2–3) for N2 and N3; clarified TODAY vs PLAN split; updated context, decision table, alternatives, consequences, signals, and follow-up tasks to reflect provider chain with Gemini primary, Sarvam secondary, deterministic fallback.
- 2026-10-02 · v1.2 · logic and truth audit fixes: updated provider registry to reflect actual implementation (Sarvam only, no Gemini integrations); revised constraints, consequences, risks, and acceptance signals accordingly.
- 2026-10-02 · v1.1 · fact-check pass: removed internal references, clarified that approved free accounts are Sarvam credits; updated wording on demo vs production data.
- 2026-10-02 · v1 · first draft.
