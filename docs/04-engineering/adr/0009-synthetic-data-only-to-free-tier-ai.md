# 0009: Synthetic data only to free-tier AI

| | |
|---|---|
| Status | Accepted as a decision, 2 Oct 2026. Enforcement today is by construction: every merchant, KYC name, sales figure and slip in the prototype is synthetic, and no code checks it. The gate described here is PLANNED (Wave 2) and does not exist yet |
| Owner | Ujjwal Pardeshi |
| Date | 2026-10-02 |
| Related | [SPEC §0.1, §3, §14](../../SPEC.md) · [AI architecture and guardrails §5](../ai-architecture-and-guardrails.md) · [Free-tier stack and setup](../free-tier-stack-and-setup.md) · [ADR 0003](0003-free-ai-provider-chain.md) · [ADR 0004](0004-live-simulated-fallback-labels.md) · [Hospital-cash claim (fs-02) §12](../../02-product/feature-specs/fs-02-hospital-cash-claim.md) · [Ask Chhatri (fs-05) §16](../../02-product/feature-specs/fs-05-ask-chhatri.md) · [Regulatory and compliance](../../05-business/regulatory-and-compliance.md) · [Facts and sources (A19, A22)](../../01-strategy/facts-and-sources.md) |

## TL;DR

Only synthetic data is sent to AI services that run on free tiers or free credits. Today that holds because the whole prototype is synthetic. No code enforces it. The planned gate is one setting, `CHHATRI_DATA_IS_SYNTHETIC` (name proposed), which every free-tier link must pass before it is called. When the setting is false or unset the links are skipped and the result is labelled `FREE_TIER_BLOCKED`. This ADR does not choose a processor for real data. That is a decision for a pilot, and §Real data lists what must come first.

## Context

**Terms of free tiers.** The Gemini free tier may use content to improve Google products (facts A19, with the pricing page as the source). Nothing in this repository records the terms of the Sarvam free credits. They are treated the same way until someone reads the terms of the plan in use and writes the result down.

**Why it matters.** A hospital slip carries a patient's name, a hospital and dates. That is health information about a person, and it is sensitive under the DPDP Act, whose Rules are phased in (facts A22). A merchant's sales, KYC name and loan are financial data. Sending any of it to a service that may reuse it would breach the merchant's trust whatever label the screen shows.

**What is synthetic.** The city, the merchants, their KYC names, the sales, the alerts and the slips are generated (SPEC §3). The three sample slips are stamped as samples and their embedded data carries `sample: true`. Weather is real public data and is not personal. The two demo merchants (S-0142, S-0907, `is_demo`) are the only ones that receive live WhatsApp messages and Sarvam audio, and that content is synthetic too.

**What leaves the server today (BUILT, commit 86575ea).**

| Call | Data sent | Provider | Condition |
|---|---|---|---|
| Intent for UNKNOWN text | The merchant's text, 500 characters at most, behind a fixed system prompt. No ids and no facts | Sarvam chat | `SARVAM_API_KEY` is set |
| Slip reading | The uploaded image, original bytes with any metadata | Sarvam document reading | key is set |
| Speech to text | The voice-note audio | Sarvam | key is set |
| Text to speech | Reply text, 2,500 characters at most | Sarvam | key is set, demo merchants only |
| Memory | Learn-loop facts: kind, time, merchant and zone ids, and a short text with ids, outcomes, amounts and dates. No names | The LLM configured for Cognee | `COGNEE_ENABLED` and an `LLM_API_KEY`, off by default |

**What will leave (PLANNED).** The Ask question (500 characters at most) with a fact sheet of display strings and the clause text, to Gemini or Sarvam. The fact sheet holds no names, phone numbers, KYC names or shop names. A cleaned copy of the slip image to Gemini or Sarvam. Voice audio to Sarvam, or to the browser's own speech service when browser recognition is used. In Chrome that service is remote, so it counts as another processor.

## Decision

**1. The rule.** Synthetic data only, to every AI service on a free tier or free credits, and to any service whose terms have not been read.

**2. Enforcement today.** By construction, nothing more. This is a real limit. A person who uploads a real photo to a running backend that has a key would send it to a free tier. The mitigations that exist or are planned are: the live demo runs on the demo laptop ([demo runbook](../../06-delivery/demo-runbook.md)), the static demo (N7, PLANNED) has no backend and calls no provider, and the first upload shows a notice (`SLIP_NOTICE` in fs-02 and `ASK_VOICE_NOTICE` in fs-05, both proposed copy, ask for sample slips and sample sentences only).

**3. The gate (planned design, not code).**

- A setting `chhatri_data_is_synthetic`, read from `CHHATRI_DATA_IS_SYNTHETIC` (name proposed). It is per deployment, not per merchant. The default is false, so a deployment that forgets to set it fails closed. The example environment file for this synthetic prototype sets it to true (planned change).
- One function, `free_tier_allowed(component)`, in the integrations layer. Every chain asks it before it calls a free-tier link. The check is not a decorator on business functions and not a list of merchant ids.
- When it says no: the link is skipped, the attempt is recorded as blocked, the result is labelled SIMULATED with `FREE_TIER_BLOCKED` ([fs-05 §10](../../02-product/feature-specs/fs-05-ask-chhatri.md)), and one audit entry notes it per request. Templates or the simulated reader answer. A photo that is not a sample then reads as unreadable and goes to a person.
- The gate state is shown in `/api/preflight`, the provider panel and the startup log.

```python
# Planned design, not code: where the gate sits in a chain.
def run_chain(component, links, request):
    attempts = []
    for link in links:
        if link.free_tier and not settings.chhatri_data_is_synthetic:
            attempts.append(Attempt(link.name, outcome="BLOCKED", reason="FREE_TIER_BLOCKED"))
            continue
        ...  # call the link, validate the reply, return on success
    return template_or_simulated_answer(component, attempts)
```

What the gate does not do: it does not look inside a payload, and it cannot tell real data from synthetic data inside a deployment that says it is synthetic. The protection is that the deployment's data is synthetic and that the flag is set honestly.

**4. What goes into prompts.** The Ask fact sheet has no names or contact details. The slip reader's prompt holds no merchant data, not even the KYC name ([fs-02 §7.3](../../02-product/feature-specs/fs-02-hospital-cash-claim.md)). The merchant's question is untrusted text and can contain anything a person types, so it is capped at 500 characters and is not written to the audit log.

**5. Logs.** Adapters never log secrets and raise errors with safe messages that hold no provider body (BUILT). The BUILT audit entry for an intent holds the merchant id, the intent and whether rules or the model chose it, and no text. The planned Ask and voice entries hold hashes and counts, not text ([fs-05 §16.3](../../02-product/feature-specs/fs-05-ask-chhatri.md)). One known exception is in the decision record: the patient name appears in the name check's text, and the audit log is append-only. Fixing it is task N3.14 in fs-02.

**6. Real data.** Out of scope here. Before any real data reaches an AI service: read the terms of the plan in use and record them, choose a processor under a data-processing agreement (a paid API, a model run locally, or the insurer's own), implement consent and deletion (fs-07), and set retention with the insurer. This ADR deliberately does not name the processor.

## Alternatives considered

1. **Send all data to free tiers.** Simplest, and the code needs no gate. Rejected: it can breach the free-tier terms, it breaches the merchant's trust and it is not a DPDP-compliant design.
2. **Synthetic data only to free tiers (chosen).** The cost is a setting, a check on each link and a separate synthetic dataset, all of which the prototype already has or needs.
3. **Local models only.** No external transfer by design. The team has not evaluated local model quality or latency for slip reading or Hindi answers, and the evaluation would cost time the waves do not have. Not chosen for the prototype. Still open for a pilot.
4. **Anonymise before sending.** Hashing names or redacting slip text does not change what the terms allow, and dates, hospital and amounts can still identify a person. Rejected as a substitute for the rule.

## Consequences

**Positive**

- No real personal data goes to a free tier, and the rule can be tested once the gate exists.
- Data provenance is clear, and tests do not depend on real data.
- The label tells a viewer when the gate closed a link.

**Negative**

- Sample data looks artificial.
- The gate is coarse: one flag per deployment.
- The gate is a setting and a check on each link, with tests for each chain.
- Until the gate exists, the rule rests on the data being synthetic.

**Risks and mitigations**

- A person uploads a real photo or types real details into the live demo. Mitigation: the notices, the backend on the demo laptop only, no backend in the static demo, and a line in the demo runbook (proposed).
- A developer commits a real image into `backend/data/slips`. Mitigation: review, and a proposed test that every file there carries the sample marker in its embedded data.
- A pilot deployment starts with the flag set to true by habit. Mitigation: the flag defaults to false and `/api/preflight` shows it.
- A log or audit entry captures a payload. Mitigation: keep the BUILT rule that logs hold safe messages and metadata only, and test it for the new adapters.

## How we will know it was right

1. A gate test with fakes: with the setting false or unset, no free-tier link is called on any chain and the label is `FREE_TIER_BLOCKED`. With it true, links are called (Wave 2).
2. `/api/preflight` and the provider panel show the gate state.
3. A test over `backend/data/slips` finds the sample marker in every file (proposed).
4. The data-flow table in [AI architecture §5](../ai-architecture-and-guardrails.md) is re-read at the end of each wave and still matches the code.

## Follow-ups

- **Wave 2, Ujjwal Pardeshi.** Add the setting and `free_tier_allowed`, wire it into every free-tier link (tasks N2.10 in fs-05 and N3.3 in fs-02), add the label, the audit entry and the preflight line, set the example environment file, and write the gate tests. The Sarvam links that exist today, and Cognee when it is enabled, are to go through the same check.
- **Wave 2, Omkar Kadam.** Show the first-use notices for slips and voice, and the gate state in the provider panel.
- **Wave 3.** With N6 (the consent centre and "forget my slip", [fs-07](../../02-product/feature-specs/fs-07-cover-purchase-and-consent.md)), mask the patient name in check text so deletion is not blocked by the audit log (fs-02 N3.14).
- **Before any pilot.** Read and record the provider terms, choose the processor, set retention and consent. These are not scheduled here.

## Open questions

1. Do the terms of the Sarvam free credits allow reuse of content? If they forbid it, the rule might be relaxed for Sarvam alone, but not for Gemini. Owner: Ujjwal Pardeshi.
2. For a pilot with real slips: a local reading model, a paid API under a data-processing agreement, or the insurer's own infrastructure? Owner: Ujjwal Pardeshi, with the insurer.
3. Should the gate be per merchant instead of per deployment? A per-deployment flag is simpler and fails closed. A per-merchant flag helps a mixed environment. Recommendation: per deployment first. Owner: Ujjwal Pardeshi.

## Changelog

- 2026-10-02 · v3 · aligned with the code and the Wave 2 specs: decision Accepted while the gate is PLANNED, stated explicitly; enforcement today is by construction; the gate is a deployment setting that fails closed and is labelled `FREE_TIER_BLOCKED`; the old decorator and its code, the claim that demo mode gates AI (it only hands the officer token to the console), the invented merchant list, the "question text only" description (the Ask call also sends a fact sheet), the Tesseract latency note, the paid-API production guidance, the unverified claim about Sarvam's terms and the 30-day log retention were removed; the data-flow table now lists what is sent today and what will be sent
- 2026-10-02 · v2 · final consistency pass against the code: no changes needed; ADR correctly enforces synthetic-only rule for all free-tier AI services (Sarvam TODAY, Gemini PLANNED).
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned: clarified that synthetic-only rule applies to EVERY free tier (Gemini + Sarvam today, and any future free service); updated context, decision, alternatives, consequences, signals, follow-ups, and open questions to reflect both Gemini (PLANNED Oct 2–3) and Sarvam (today); added guard implementation for Gemini; expanded privacy checklist.
- 2026-10-02 · v1.2 · logic and truth audit fixes
- 2026-10-02 · v1.1 · fact-check pass: clarified terminology throughout (demo vs production data); updated guard error message; reworded post-launch guidance to note DPDP compliance (A22) and preference for local models over free-tier APIs.
- 2026-10-02 · v1 · first draft.
