# 0009: Synthetic data only to free-tier AI

| | |
|---|---|
| Status | Accepted |
| Owner | Ujjwal Pardeshi |
| Date | 2026-10-02 |
| Related | [SPEC §0.1, §14](../../SPEC.md) · [Free-tier stack and setup](../free-tier-stack-and-setup.md) · [AI architecture and guardrails](../ai-architecture-and-guardrails.md) · [Facts and sources (A19)](../../01-strategy/facts-and-sources.md) |

## TL;DR

Demo merchants (Anil S-0142, Ramesh S-0907), sample hospital slips, and simulated sales data are sent to free-tier AI services (Sarvam today; Gemini once its adapter is live in Oct 2–3). Personal data and merchant records (hospital slips from real patients, actual account numbers, real KYC data) are never sent to any free-tier service. This complies with free-tier terms of service (A19: Gemini may use inputs to improve products) and DPDP privacy requirements (A22). Demo data is labelled SIMULATED in the console; judges know it is not real and synthetic.

## Context

**Free-tier AI terms (A19):** Free-tier services (Gemini, Sarvam) may use inputs to improve products. This means systems may log, analyze, and use prompts and responses to train future models. If a real hospital slip (with a patient's name, hospital, medical condition) is sent, that data is now in the free service's training pipeline. Gemini's terms explicitly state: "your content may be used to improve Google products" (A19).

**Privacy concern:** a merchant's health data (hospital slip) and financial data (sales, loan, KYC) are sensitive under India's DPDP Act (A22). Sending real personal data to a free service (even synthetic-labeled) violates the merchant's trust and compliance obligations.

**Demo readiness:** Chhatri's demo uses fictional merchants (Anil S-0142, Ramesh S-0907) and sample slips (a generic KEM Hospital discharge for "Anil R. Jadhav"). These are safe to send to free services; they are not personally identifiable.

**Mechanism TODAY (Sarvam only):** The demo includes a "demo mode" flag. When enabled, all Sarvam calls use synthetic data (demo merchants, sample slips). When disabled (production), a guard blocks any call to free-tier services; only paid APIs or local models process merchant data (roadmap).

**Mechanism PLAN (Gemini + Sarvam, Oct 2–3):** The same demo-mode guard applies to Gemini calls once the adapter is live. Gemini and Sarvam will both receive only synthetic demo data during the hackathon; production will require paid APIs or local vision models (ADR 0003 post-launch guidance).

## Decision

**Free-tier gating rule:** **Synthetic data only to every free-tier AI service.** This applies to:
- Sarvam free credits (today)
- Gemini free tier (once adapter is live, Oct 2–3)
- Any other free-tier service (future)

Implementation (backend/chhatri/config.py, SPEC §0.1):

```python
# Decorator on every external AI call
@check_free_tier_data(allowed_demo_merchants=['S-0142', 'S-0907', 'S-DEMO-*'])
def ask_chhatri_with_gemini(question: str, merchant_id: str) -> Answer:
    if not DEMO_MODE and is_free_tier_provider('gemini'):
        if merchant_id not in DEMO_MERCHANTS:
            raise ValueError("Free-tier processing restricted to demo merchants in this mode")
    # Proceed to call Gemini or Sarvam
    ...

if DEMO_MODE:
    # Activate free-tier providers
    # Data: demo merchants (S-0142, S-0907, S-DEMO-*), sample slips, simulated sales
    use_gemini_free = True  # Oct 2–3: enable Gemini adapter
    use_sarvam_free = True
    use_offline_tools = True
else:
    # Production: use paid APIs or local models only
    use_gemini_free = False
    use_sarvam_free = False
    use_offline_tools = True  # Tesseract, local vision models always OK
```

**What is synthetic (safe to send to free-tier services):**

| Component | Synthetic data (free-tier safe) | Real data (production only) |
|---|---|---|
| **Merchants** | Anil S-0142 (Z7), Ramesh S-0907 (Z3), Priya (Delhi roadmap), Rajesh (officer) | (none in demo) |
| **Hospital slips** | Sample KEM Hospital discharge, "Anil R. Jadhav", 2025-08-20, "Viral fever" diagnosis redacted | (none; real slips never sent to free tier) |
| **Sales data** | Simulated hourly sales, driven by real rainfall, 2024–2025 | (none in demo; model trained on simulated data) |
| **Alerts** | IMD red alert A-20250818-01, actual alert data structure but mocked zone coverage | (none; real alerts in production only) |
| **KYC** | "ANIL RAMESH JADHAV", aadhaar and PAN format but fake numbers | (none in demo; real KYC never sent to free tier) |
| **Policy context in Ask Chhatri** | Merchant's decision facts (expected sales, premium amount) from demo scenario | (none in demo; real merchant facts never sent to free tier) |

**What calls free-tier AI or offline tools (demo mode only):**

| Callsite | Data sent | Free-tier service | Processing | Status |
|---|---|---|---|---|
| Ask Chhatri (N2): merchant question in Hindi/English | Question text only (max 500 chars, no metadata) | Gemini (PLANNED Oct 2–3) or Sarvam (today) | API call (question → answer) | OK for free tier (text-only, no PII) |
| Slip reading (N3): upload sample slip image | Sample slip PNG (demo merchant name "Anil", no real patient data, diagnosis redacted) | Gemini Vision (PLANNED Oct 2–3) or Sarvam Vision (today) | Vision API call (image → extracted fields) | OK for free tier (demo data labelled synthetic) |
| Intent detection: merchant's WhatsApp message | Text only, no metadata | Sarvam sarvam-105b (if UNKNOWN intent) | API call (text → intent) | OK for free tier (text-only, high entropy) |
| Slip reading (N3) fallback: low confidence | Sample slip PNG | Tesseract hin+eng (local) | Local OCR, no external call | OK (offline) |

**Guard implementation:**

A `@check_free_tier_data` decorator on every Gemini or Sarvam call (applies to both providers):

```python
@check_free_tier_data(provider='gemini')  # or 'sarvam'
def ask_chhatri_gemini(question: str, merchant_id: str, facts: dict) -> Answer:
    # Before calling Gemini or Sarvam:
    if not DEMO_MODE and is_free_tier_provider():
        # In non-demo mode, free-tier calls are forbidden (use paid APIs instead)
        raise ValueError("Free-tier processing is disabled in production mode. Use paid APIs.")
    
    if DEMO_MODE:
        # In demo mode, allow only demo merchants
        if merchant_id not in DEMO_MERCHANTS:
            raise ValueError(f"Free-tier processing restricted to demo merchants: {DEMO_MERCHANTS}. Got {merchant_id}.")
        # Sanitize facts: remove real-valued fields, keep only expected_sales, premium, etc.
        facts_sanitized = {k: v for k, v in facts.items() if k in ALLOWED_FACT_FIELDS}
    
    # For offline tools (Tesseract, local models), no guard needed (no external call)
    # Call Gemini or Sarvam with question + sanitized facts
    return call_gemini_or_sarvam(question, facts_sanitized)
```

**Demo label (SPEC §0.1):**

Every AI-processed result shown in the UI includes a badge showing status and which provider was used:

```
Ask Chhatri: SIMULATED (demo data, deterministic template)
or
Ask Chhatri: LIVE Gemini (demo data, Gemini free tier)
or
Ask Chhatri: LIVE Sarvam (demo data, Sarvam free tier)

Slip reading: SIMULATED (demo data, embedded JSON)
or
Slip reading: LIVE Gemini (demo data, Gemini Vision)
or
Slip reading: LIVE Sarvam (demo data, Sarvam Vision)
or
Slip reading: LIVE Tesseract (demo data, local OCR)
```

When production keys are set (post-hackathon), the badge changes to show paid API status:

```
Slip reading: LIVE Claude API (merchant data via paid API, real slips allowed)
```

**Post-launch guidance (after the hackathon, for production):**

1. **Vision (slip reading, N3):** Use Claude API (paid) or local vision models (ONNX, TinyVLM) for slip reading. Never send real hospital slips to free-tier vision services. Preferred path: local ONNX model (no external calls, DPDP-safe).
2. **Grounding (Ask Chhatri, N2):** For production, use Claude API (paid) or fine-tuned open-source models deployed locally (with LoRA or similar). Sarvam free tier is NOT acceptable for production (terms allow data reuse for training).
3. **Intent detection:** Sarvam free tier acceptable if: (a) DEMO_MODE is off, (b) only non-sensitive queries are sent (no merchant context, no PII), (c) explicit DPDP consent is obtained.
4. **All sensitive data:** Slip images, decision facts, merchant records are stored in Paytm infrastructure only. External services (free or paid) receive only sanitized questions and policy context (no merchant ID, no decision facts).
5. **DPDP compliance (A22):** Implement consent journeys for each data type: Ask Chhatri consent (Q&A), slip upload consent (vision processing), speech consent (STT). Merchants can request data deletion via N6 consent centre (future).

## Alternatives considered

1. **Send all data to free tier (rejected):** Use Gemini and Sarvam free-tier services with real merchant personal data and health records. Pro: simplifies code; no guard logic needed. Con: **violates privacy (DPDP A22)**; **violates free-tier terms (A19: "content may be used to improve products")**; sets bad precedent for pilot; judges may lose trust; merchants' data could be used to train future models.

2. **Synthetic data only to free tier (CHOSEN, this ADR):** Demo merchants (S-0142, S-0907), sample slips, simulated sales sent to Gemini and Sarvam free tiers. Pro: **DPDP compliant**; **respects free-tier terms**; judges see real AI without privacy violation; pilot-ready roadmap (move to paid APIs). Con: adds `@check_free_tier_data` guard logic; requires separate demo dataset; tests must use DEMO_MODE flag.

3. **Use only local models (rejected):** Run all AI locally (Ollama, TinyVLM for slip vision, Tesseract for OCR, local intent classifier). Pro: no external calls; DPDP-safe by design. Con: slip vision quality poor; latency high (5–10 min on demo laptop); judges do not see "live AI" integration; demo looks slow and local.

4. **Data anonymization (rejected):** Hash merchant names, redact slip text, anonymize KYC before sending to free tier. Pro: reduces identifiability. Con: does NOT solve the core problem: free-tier T&S allow data reuse for training; anonymized data can still be re-identified (attack risk); not a DPDP compliance solution; still violates merchant trust.

## Consequences

**Positive:**

- **DPDP compliant (A22):** Merchants' personal data (KYC, slip images, health records) are protected. No real data sent to external free-tier services.
- **Free-tier T&S respected (A19):** Demos data sent to Gemini and Sarvam is explicitly synthetic and labelled. If either service reuses it for training, it is not personal data. Chhatri retains integrity.
- **Audit-ready:** Synthetic data provenance is clear (S-0142, S-0907, sample slips). Privacy review can verify no real data was sent. Roadmap clearly states: "paid APIs for production."
- **Pilot transition:** Post-hackathon roadmap is clear: use Claude API (paid) or local models, implement DPDP consent journeys, store all sensitive data in Paytm infrastructure only. Judges see strategic thinking.
- **Testable and deterministic:** Synthetic data is repeatable; tests do not depend on real merchants. Demo flow is consistent across runs.
- **Judges' trust:** Team demonstrates privacy-first mindset and regulatory awareness. Not taking shortcuts = good signal.

**Negative:**

- **Demo data "feels" artificial:** Sample slips are obviously demo data (everyone named "Anil", synthetic addresses). Judges might ask, "Is this real-world representative?" Mitigate: add 1–2 realism touches (date ranges, varied hospital names, multi-line addresses).
- **Code complexity:** `@check_free_tier_data` decorator adds ~50 LOC and test surface area. Must test: demo merchants pass guard, non-demo merchants fail in non-DEMO_MODE.
- **Guard overhead:** Data-type checks add ~5ms per call (negligible). Tesseract latency ~1–2s per image (acceptable for N3 pre-check).

**Risks:**

- **Accidental real data in code:** if a developer hardcodes a real merchant ID in a test, the guard should catch it. Mitigate: (a) enforce DEMO_MODE=true in test suite, (b) add lint rule that rejects non-S-\* merchant IDs in source, (c) code review checklist: "No real merchant IDs."
- **Data leakage in logs:** if Chhatri logs full API requests (slip images) or responses, the log could contain real data if accidentally triggered. Mitigate: (a) log only metadata (merchant_id, provider, extraction result), not image/request body, (b) sanitize merchant_id in logs, (c) implement log retention policy (delete after 30 days).
- **Gemini quota depletion:** If Gemini free quota is lower than expected (e.g., 50 calls/day), demo could exhaust it before Oct 3 midday testing. Mitigate: (a) profile Gemini quota on Oct 2 morning, (b) use provider panel (X6) to disable Gemini in tests, allow Sarvam only, (c) have fallback template plan if Gemini becomes unavailable.

## How we will know it was right

**Signals:**

1. All Gemini and Sarvam API calls in tests use demo merchants (S-0142, S-0907, S-DEMO-*); no real merchant IDs are found in source code, logs, or API payloads.
2. The console shows badges indicating data source: `SIMULATED (demo data, deterministic template)`, `LIVE Gemini (demo data, Gemini free tier)`, `LIVE Sarvam (demo data, Sarvam free tier)`. Judges see "demo" label and understand the data is synthetic.
3. Gemini and Sarvam API request/response logs (exported from Google Cloud and Sarvam dashboards on Oct 4) show only demo data: sample slip images (KEM Hospital, "Anil R. Jadhav"), demo merchant questions. No personally identifiable data: merchant names, KYC, slip images from real patients, or sales data from actual merchants.
4. The guard test: run a unit test that attempts to send non-demo merchant ID (e.g., "M-12345") to Gemini in DEMO_MODE=false; verify it raises `ValueError` with message "Free-tier processing restricted to demo merchants."
5. A privacy review by the team (or a mentor/judge) on Oct 3 confirms: (a) no personally identifiable data (merchant IDs, KYC, slip images) in demo; all data is synthetic and demo-labelled, (b) synthetic data is clearly marked in console badges, (c) post-launch roadmap addresses DPDP compliance via paid APIs (Claude) or local models (ONNX) when processing actual merchant data in the pilot.
6. Code audit: grep for hardcoded merchant IDs, slip file paths, KYC data. Result: only demo merchants (S-0142, S-0907) and sample-slip paths found (no real IDs, no real file paths).

## Follow-ups

- **Task (Ujjwal, Oct 2 morning):** Implement the `@check_free_tier_data` decorator and guard logic for Gemini and Sarvam calls. Check both demo merchant ID and DEMO_MODE flag before any external AI call.
- **Task (Ujjwal, Oct 2 morning):** Create `DEMO_MERCHANTS` constant in backend/chhatri/config.py: `['S-0142', 'S-0907', 'S-DEMO-*']`. Create sample-slip file list in the same file.
- **Task (Ujjwal, Oct 2 afternoon):** Implement unit test `test_guard_blocks_non_demo_merchant_in_non_demo_mode()`: attempt to call Gemini/Sarvam with merchant_id="M-12345" in DEMO_MODE=false; verify ValueError is raised.
- **Task (Ujjwal, Oct 2 afternoon):** Update logger to redact merchant_id in Gemini/Sarvam request logs. Log only metadata: `{provider: 'gemini', merchant_id: 'S-0142', latency_ms: 1234, result: 'success'}`, never the slip image or full request payload.
- **Task (Ujjwal, Oct 3 morning):** Code audit: run grep for hardcoded merchant IDs, slip paths, KYC data. Verify no real IDs in codebase. Generate audit report.
- **Task (Team, Oct 3 morning):** Privacy checklist: (a) Gemini API key is env-only (not in code), (b) sample-slip images do not contain real names, (c) demo merchants use S-* prefix consistently, (d) post-launch roadmap is documented (ADR 0003 post-launch guidance).
- **Task (Team, Oct 4 after demo):** Export Gemini and Sarvam API logs; verify only demo data was sent. Generate privacy audit report for judges/mentors.

## Open questions

1. Should demo merchants be hardcoded in config.py, or loaded from a config file for flexibility? Owner: Ujjwal Pardeshi. Recommendation: hardcode initially (simpler, no extra file); refactor to config file if pilot needs to add more demo merchants.
2. Can Sarvam's free-tier terms of service be reviewed to confirm whether free credits have the same "content reuse for training" clause as Gemini (A19)? Owner: Ujjwal Pardeshi. Impact: if Sarvam does NOT allow reuse, synthetic-only rule can be relaxed for Sarvam (but not Gemini).
3. For production pilot (post-hackathon), should local slip vision (ONNX, TinyVLM) be prioritized over Claude API, given cost and DPDP compliance? Owner: Ujjwal Pardeshi. Recommendation: start with local ONNX (DPDP-safe); only use Claude API if local quality is poor.
4. Should the `@check_free_tier_data` guard be implemented as a decorator or as middleware (guard in integrations/registry.py)? Owner: Ujjwal Pardeshi. Recommendation: middleware in registry; less boilerplate, easier to audit all providers in one place.

## Changelog

- 2026-10-02 · v2 · final consistency pass against the code: no changes needed; ADR correctly enforces synthetic-only rule for all free-tier AI services (Sarvam TODAY, Gemini PLANNED).
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned: clarified that synthetic-only rule applies to EVERY free tier (Gemini + Sarvam today, and any future free service); updated context, decision, alternatives, consequences, signals, follow-ups, and open questions to reflect both Gemini (PLANNED Oct 2–3) and Sarvam (today); added guard implementation for Gemini; expanded privacy checklist.
- 2026-10-02 · v1.2 · logic and truth audit fixes
- 2026-10-02 · v1.1 · fact-check pass: clarified terminology throughout (demo vs production data); updated guard error message; reworded post-launch guidance to note DPDP compliance (A22) and preference for local models over free-tier APIs.
- 2026-10-02 · v1 · first draft.
