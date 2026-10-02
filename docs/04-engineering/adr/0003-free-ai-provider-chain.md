# 0003: Free AI provider chain

| | |
|---|---|
| Status | Accepted |
| Owner | Ujjwal Pardeshi |
| Date | 2026-10-02 |
| Related | [SPEC §0.1](../../SPEC.md) · [Free-tier stack and setup](../free-tier-stack-and-setup.md) · [Facts and sources (A17, A19)](../../01-strategy/facts-and-sources.md) |

## TL;DR

Chhatri uses a provider chain for each AI need: try primary → fallback → deterministic. TODAY: **Grounding** (Ask Chhatri, N2): Sarvam sarvam-105b (free credits) → deterministic templates. **Vision** (slip reading, N3): Sarvam Vision doc-ai (free credits) → Tesseract OCR (offline). **Speech** (N4): Sarvam Saaras/Bulbul (free credits) → browser Web Speech API → tap chips. PLAN (Oct 2–3): Add **Gemini free-tier adapter as the first provider** for N2 and N3, making the chain: 1. Gemini (PLANNED) → 2. Sarvam (existing) → 3. Deterministic fallback. Cognee (memory) and n8n (workflows) are kept optional; the in-process runner is the default. This keeps costs to zero and maximizes demo resilience.

## Context

**TODAY (commit 86575ea, 2 Oct):** Sarvam adapters are live for chat (sarvam-105b), vision (doc-ai), speech (Saaras v3/v4, Bulbul v3) with free starter credits. NO Gemini adapter is integrated yet. NO Tesseract fallback is deployed yet.

**PLAN (2–3 Oct):** The team will add Gemini free-tier adapter as the FIRST provider (PLANNED) for Ask Chhatri (N2) and slip reading (N3). This keeps Sarvam as the second provider and maintains deterministic fallbacks as the final chain link.

**Approved free accounts:** Google AI Studio (Gemini free tier, approved for pilot) and Sarvam free credits (approved). WhatsApp Cloud API is not funded. No budget for paid APIs during hackathon.

**Opportunity:** Free models are now capable. Gemini's free-tier text and vision models handle English and Hindi. Sarvam's chat, Saaras, and Bulbul handle Indian languages and regional contexts well. Tesseract (optional local OCR) is open-source. Fallbacks are fast and deterministic (word lists, regex, templates, browser APIs). Provider chain enables per-component control and ensures demo resilience.

**Sequencing:** if a provider is down or quota-exhausted, the next chain link fires without latency. Per-component toggles (X6 provider panel, H7) let the team choose which provider is active on stage (e.g., use Sarvam only to preserve Gemini quota, or switch to deterministic templates if both are slow).

## Decision

**Provider registry** (backend/chhatri/integrations/registry.py, SPEC §0.1). TODAY (as of commit 86575ea): only Sarvam is live. PLAN (Oct 2–3): activate Gemini as provider 1 for N2 and N3.

| Need | Provider 1 (PRIMARY) | Provider 2 | Provider 3 (FALLBACK) | Status |
|---|---|---|---|---|
| Ask Chhatri (N2) grounding | Gemini free tier | Sarvam sarvam-105b (free credits) | Deterministic templates | PLANNED: Gemini Oct 2–3; TODAY: Sarvam LIVE with key |
| Slip reading (N3) vision | Gemini Vision | Sarvam Vision doc-ai (free credits) | Tesseract hin+eng (local, offline) or REFERRED | PLANNED: Gemini Oct 2–3; TODAY: Sarvam LIVE with key |
| Intent detection (UNKNOWN only) | Sarvam sarvam-105b (free credits) | Rule-based lexicon | — | TODAY: Sarvam LIVE with key; rules always available |
| Speech-to-text (N4) | Sarvam Saaras v3/v4 (free credits) | Browser Web Speech API | Tap-to-send chips (no speech) | TODAY: Sarvam LIVE with key |
| Text-to-speech (N4) | Sarvam Bulbul v3 (free credits) | Browser speechSynthesis | Text only | TODAY: Sarvam LIVE with key |
| Workflows (orchestration) | In-process runner (code, same day) | n8n CE self-hosted (shown, not live on stage) | — | TODAY: in-process |
| Memory (optional) | Cognee (open source, optional) | Networkx graph (in-process) | — | TODAY: in-process graph |

**Integration flow:**

1. On startup, `build_integrations()` reads env vars (SARVAM_API_KEY, etc.).
2. If a key is set and the provider is reachable, it is marked LIVE. Otherwise, SIMULATED.
3. On each call, try primary. If it fails (timeout, quota, error), fall back. Log the switch.
4. A provider-panel header in the console shows which mode is active for each component (X6, H7).

**Free-tier usage limits (A17, A19):**

- Sarvam: free starter credits (amount not published, A17); free-form use covers the demo.
- Tesseract: no limit (local, open source).
- Browser Web Speech API: no limit (local).

**Privacy rule:** Send only synthetic demo data to Sarvam (demo merchants like Anil S-0142, sample slips) and never personal data or merchant records (facts-and-sources.md §D: sales data is simulated for now).

## Alternatives considered

1. **Gemini + Sarvam chain (CHOSEN):** Activate Gemini free tier as provider 1 (Oct 2–3), keep Sarvam as provider 2 (existing code), then deterministic fallback. Pro: best quality (Gemini state-of-the-art for text and vision); Sarvam excellent for Hindi/regional context and speech; flexible provider control (X6 panel); resilient if either provider is slow or down. Con: requires Gemini API key setup; Gemini quota unknown (estimated sufficient for 3–7 min demo); adds code complexity for adapter. Risk: quota exhaustion mid-demo mitigated by fallback chain and per-component toggle.

2. **Sarvam only (rejected):** Keep the current single-provider chain (Sarvam → deterministic fallback). Pro: simpler code (no Gemini adapter); existing code already works. Con: less resilience if Sarvam is down or slow; misses opportunity to leverage Gemini's superior text quality; judges expect "two free-tier providers" per team's pre-demo notes. Outcome: chosen over for Oct 2–3 build, but kept as existing provider 2.

3. **Local-only AI (rejected):** Ollama or TinyLLM on the demo laptop. Pro: no external dependency; no quota; fully offline. Con: latency is high (5–10 min for some models); no good Hindi models in local libraries; slip vision quality poor; demo looks fake. Does not meet judges' expectations for "live AI."

4. **Paid APIs (rejected):** Use Claude API (paid) or other paid providers. Pro: best quality. Con: budget is zero; hackathon is student phase, not production; demo risk if quota exhausted mid-show; not in spirit of free-tier challenge. Deferred to post-hackathon roadmap.

5. **Mock all AI (rejected):** Deterministic simulators everywhere (no external calls). Pro: fully deterministic; no quota risk; simple setup. Con: demo looks fake; judges see "vision" reading embedded JSON, not a real model; fails the "live AI" expectation. Kept only as fallback when providers are unavailable.

## Consequences

**Positive:**

- **Zero cost:** Gemini free tier and Sarvam starter credits are both free. Combined quota estimated sufficient for a 3–7 minute demo.
- **High-quality output with two providers:** Gemini's text and vision models are strong; Sarvam excels at Hindi/regional context and speech. Two providers = two chances for good coverage and fallback resilience.
- **Resilience:** if Gemini is slow or down, Sarvam fires automatically; if both are slow, deterministic fallback is available. No manual intervention needed.
- **Privacy-safe:** no real data sent to external services; synthetic demo data only; compliance ready (ADR 0009).
- **Verifiable:** the provider chain is transparent; every call is logged; X6 provider panel shows which provider was used and its status.
- **Flexible control:** team can toggle providers on stage (X6 panel, H7) to manage quota and latency in real time.
- **Deterministic fallbacks:** if both Gemini and Sarvam are unavailable, deterministic templates, Tesseract, and browser APIs still work (no call fails entirely).

**Negative:**

- **Quota risk:** Gemini and Sarvam free-tier quotas are not published. Demo could exhaust them if used heavily. Mitigation: per-component toggles (X6) let team enable only hero moments; profile quotas on 2 Oct morning.
- **Code complexity:** Gemini adapter (~200 LOC) adds engineering complexity and test surface area. Mitigated by clear module structure (integrations/gemini_*.py following sarvam_*.py pattern).
- **Latency variance:** primary + fallback logic adds ~200ms overhead if primary times out before fallback starts. Mitigated by setting tight timeouts (3–5s).
- **Quality variability:** free models weaker than paid Claude API. Gemini may hallucinate on unfamiliar contexts; Sarvam vision may fail on blurry photos.

**Risks:**

- **Gemini quota exhaustion:** free tier quota unknown; demo could run out mid-show. Mitigate: profile live calls on 2 Oct morning; cache common Ask Chhatri questions; test fallback templates in isolation; team has final say via X6 toggle to disable Gemini on stage if needed.
- **Sarvam fallback not sufficient:** if both Gemini and Sarvam are down, only deterministic templates remain for Ask Chhatri and Tesseract for slip reading. Mitigate: this is still acceptable (demo shows policy engine works); pre-test templates and Tesseract on demo laptop with no internet (N3 pre-check + N4 offline paths).
- **Gemini API key exposure:** API key must be in environment or config. Mitigate: never commit to repo; use .env (gitignored); rotate after demo; use strict project-level API quotas in Google Cloud Console.
- **Provider choice confusion on stage:** if team manually toggles X6 panel during demo, judges may question decision. Mitigate: pre-decide provider strategy (e.g., "Gemini first for text, Sarvam for speech to preserve Gemini quota"); document in setup guide.

## How we will know it was right

**Signals:**

1. Demo completes with both Gemini and Sarvam live; provider chain switches work as expected (can verify via X6 panel and console logs on 2 Oct evening setup).
2. Gemini adapter is live by Oct 3, 17:00 UTC; Ask Chhatri questions are answered by Gemini free tier (text quality matches or exceeds Sarvam).
3. Slip reading extracts name, dates, hospital via Gemini Vision (Oct 3) or Sarvam Vision; ≥80% confidence on demo slips; pre-check catches issues before policy checks run (N3, H5).
4. Fallback paths (Tesseract, deterministic templates, browser Speech API) work without external calls (tested on the demo laptop with no internet, N3 and N4 offline paths).
5. X6 provider panel shows correct status for each component (LIVE, SIMULATED, FALLBACK); console logs show provider switches when a primary times out or fails.
6. Ask Chhatri answers a merchant question in <5 s (Gemini or Sarvam); intent detection in <1 s if both LLM providers are down (rules only).
7. On 3 Oct 17:00 during the demo, the team can confirm: Gemini API key is active → Gemini is marked LIVE in X6 → at least one Ask Chhatri question is answered by Gemini (verifiable in logs or UI badge).

## Follow-ups

- **Task (Ujjwal, Oct 2 morning):** Set up Gemini free-tier API key (Google AI Studio) and verify quota. Profile Gemini latencies on Ask Chhatri (N2) and slip reading (N3) with sample requests.
- **Task (Ujjwal, Oct 2 afternoon):** Implement Gemini adapter (backend/chhatri/integrations/gemini_*.py) following sarvam_*.py pattern. Add provider registry entries for Gemini as provider 1 for N2 and N3.
- **Task (Ujjwal, Oct 2 evening):** Test Gemini + Sarvam fallback chain in isolation (unit tests); verify timeout and retry logic.
- **Task (Team, Oct 2 evening):** Test provider chain on demo laptop with X6 panel toggle. Verify Gemini and Sarvam both report LIVE status; test fallback to Tesseract (N3) and deterministic templates (N2) by unplugging internet or disabling keys.
- **Task (Team, Oct 3 morning):** Verify Sarvam API key and credits on demo morning; test quota sufficiency with a few live calls (speech, vision, chat).
- **Task (Team, Oct 3 morning):** Test browser Web Speech API and Tesseract on the demo laptop (N4 fallback, N3 local OCR; must work offline).
- **Task (Team, Oct 3 morning):** Run end-to-end flow: Ask Chhatri question → Gemini response (verify in logs); upload slip → Gemini Vision extraction (verify badge shows LIVE); verify provider logs show Gemini was called first.
- **After the hackathon:** Post-demo retrospective: which provider was faster (Gemini or Sarvam)? Which had better quality? Recommend provider priority for production stack (roadmap).

## Open questions

1. Can Gemini API quota be increased beyond free tier for the pilot phase (post-hackathon)? Owner: Ujjwal Pardeshi.
2. Can Sarvam free-tier credits be extended beyond the starter pack for the pilot? Owner: Ujjwal Pardeshi.
3. For production (after pilot), should the provider priority be: (a) Gemini first (lower cost, better quality), (b) Sarvam first (existing integration, good Hindi), (c) local Cognee + vector search (no external calls)? Owner: Ujjwal Pardeshi.
4. Should Tesseract be replaced with a local ONNX model for faster OCR, or is 1–2 s latency acceptable? Owner: Ujjwal Pardeshi.
5. For Ask Chhatri grounding, should Gemini use the same system prompt and guard logic as Sarvam, or a Gemini-specific prompt? Owner: Ujjwal Pardeshi.

## Changelog

- 2026-10-02 · v2 · final consistency pass against the code: no changes needed; ADR correctly describes the provider chain (Gemini PLANNED, Sarvam TODAY) and synthetic-only rule for free tiers.
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned: restored Gemini free tier as PLANNED first provider (Oct 2–3) for N2 and N3; clarified TODAY vs PLAN split; updated context, decision table, alternatives, consequences, signals, and follow-up tasks to reflect provider chain with Gemini primary, Sarvam secondary, deterministic fallback.
- 2026-10-02 · v1.2 · logic and truth audit fixes: updated provider registry to reflect actual implementation (Sarvam only, no Gemini integrations); revised constraints, consequences, risks, and acceptance signals accordingly.
- 2026-10-02 · v1.1 · fact-check pass: removed internal references, clarified that approved free accounts are Sarvam credits; updated wording on demo vs production data.
- 2026-10-02 · v1 · first draft.
