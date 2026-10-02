# 0008: In-process workflows on stage

| | |
|---|---|
| Status | Accepted |
| Owner | Ujjwal Pardeshi |
| Date | 2026-10-02 |
| Related | [SPEC §8, §24.1](../../SPEC.md) · [System architecture §2.2](../system-architecture.md) · [Free-tier stack and setup](../free-tier-stack-and-setup.md) |

## TL;DR

The demo uses an **in-process workflow runner** (code, same as production logic) instead of live n8n. This avoids external dependencies, replay timing issues, and demo fragility. n8n is shown as the **production orchestration** (it has a 30–60 s hold for batch operations), but for a 3-minute demo, the in-process runner is deterministic and fast. Both execute the same workflow DAG; the difference is only deployment.

## Context

**Workflow needs:**

Chhatri orchestrates multi-step sequences that need to:

1. **Deterministic timing:** the same scenario seed must produce identical event timings (audit trail).
2. **Replay compatibility:** workflows must run against a simulated clock (6 minutes per real second), not wall time.
3. **Stage readiness:** on-site demo has no staging n8n server; internet is best-effort; external dependencies fail.
4. **Observability:** every step is logged; judges can trace a payout from decision to credit.

**n8n advantages:** visual workflow editor, audit trail, error handling, retries, templates. **n8n disadvantages for a demo:** external dependency, no offline mode, clock integration is complex, setup on the demo laptop is fragile.

**In-process alternative:** Python code that runs the same DAG, with the same states (Pending, Running, Completed, Failed), same retry logic, same logging.

## Decision

**Default: in-process runner** for the demo (staging, development, and on-site).

The in-process runner is a simple orchestrator:

```python
# backend/chhatri/workflows/engine.py
class WorkflowEngine:
    def run(self, workflow_id: str, inputs: dict) -> WorkflowResult:
        # Execute a DAG of tasks; clock is passed in (can be manual or system)
        # Logging: each step, input, output, latency, error
        # Retry logic: exponential backoff for transient errors
```

**Workflows** (currently):

1. **`area_claim_payout`:** trigger detection → for each shop: policy check → create decision → credit payout → log audit entry.
2. **`personal_claim_payout`:** slip extraction → pre-check → policy check → create decision → credit payout → log audit entry → EDI request.
3. **`edi_holiday_request`:** payout decision → format request → send to lender → log response.
4. **`ask_chhatri_answer`:** merchant question → intent detect → ground in policy → guard checks → format answer.

Each workflow is defined as a Python class with `execute()` method and state transitions.

**n8n as production orchestration:**

In the docs and pitch, we say:

> "Production uses n8n, which adds workflow versioning, audit, and retry policies. The demo shows the logic in-process for simplicity."

A diagram in [system-architecture.md](../system-architecture.md) shows n8n as the production box, with the note: "n8n CE self-hosted, orchestrates workflows and holds a 30–60 s clock for batch operations."

**Why a 30–60 s hold?** n8n can batch multiple merchants' payouts, so instead of crediting each shop instantly, it collects a batch and credits them together via the settlement rail (realistic, lower transaction cost).

**Console provider panel:** n8n status is always FALLBACK on stage (not LIVE), with the reason "in-process runner active."

## Alternatives considered

1. **Live n8n on stage (rejected):** deploy n8n CE self-hosted on the demo laptop, run workflows live. Pro: real production setup. Con: n8n takes 30–60 s per workflow (not 4 minutes); clock integration is complex; if n8n is down, payouts stall; setup is fragile; judges may miss the payout because of the hold.

2. **No workflows; inline code (rejected):** put all orchestration in the main API handler (no DAG, no retries, no audit trail). Pro: simplest. Con: not scalable; hard to test; n8n cannot replace it post-launch; error handling is ad-hoc.

3. **Mock all workflows (rejected):** deterministic simulators that skip the workflow engine entirely. Pro: fastest. Con: does not demonstrate orchestration at all; misleading on what is production.

## Consequences

**Positive:**

- **Reliability:** no external dependency; works offline; demo is deterministic and repeatable.
- **Speed:** in-process workflows run in milliseconds; payout from decision to credit in 4 minutes simulated time (10 s real time).
- **Observability:** every step is logged; judges can see the workflow trace in the audit log.
- **Pilot-ready:** the in-process runner can be replaced by n8n post-launch without changing the workflow definitions.
- **Learning:** the team demonstrates understanding of orchestration patterns (DAGs, state, retries, logging).

**Negative:**

- **Not production:** the demo is not running the actual production stack. Mitigate: clearly state "for stage, in-process; for production, n8n" in the pitch.
- **Limited error simulation:** the in-process runner has basic retry logic; it does not show n8n's advanced error handling (webhooks, conditional routes, etc.).

**Risks:**

- **Logic divergence:** if the in-process runner and n8n implementations differ, post-launch bugs arise. Mitigate: define workflows as specs (YAML or similar), not code; both implementations follow the spec.
- **Latency expectations:** judges see 4-minute payouts on stage but may expect instant payouts in production. Mitigate: mention the n8n 30–60 s hold in the pitch; explain why batching is realistic (lower cost).

## How we will know it was right

**Signals:**

1. The demo payout fires deterministically at 17:04 (simulated), every time (tested with seed).
2. The audit log shows every workflow step (detection, policy, decision, payout, EDI) with timestamps and latencies.
3. Judges understand that n8n is the production orchestration (explained in the pitch).
4. If a workflow step fails on stage (e.g., policy check fails), the audit log shows the error and the next state (REFERRED or BLOCKED).
5. A partner lender can understand the EDI request flow from the workflow docs, not just the code.

## Follow-ups

- **Task:** Define each workflow as a spec (YAML or ADR section) with inputs, steps, outputs, error cases.
- **Task:** Implement in-process runner with logging, state transitions, retries (Ujjwal, roughly 4 hours).
- **Task:** Write tests for each workflow (happy path, errors, retries).
- **Task:** Document n8n migration path for post-launch (roadmap).

## Open questions

1. Should workflows be stored in a database (allowing live edit on stage), or in YAML files (require a code restart)? Owner: Ujjwal Pardeshi.
2. If a workflow fails mid-execution (e.g., Sarvam is down), should the in-process runner retry, or immediately mark the task as REFERRED (human)? Owner: Ujjwal Pardeshi.

## Changelog

- 2026-10-02 · v2 · final consistency pass against the code: no changes needed; ADR correctly describes in-process workflows as demo default with n8n as production path.
- 2026-10-02 · v1 · first draft.
