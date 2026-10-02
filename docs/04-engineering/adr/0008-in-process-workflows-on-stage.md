# 0008: In-process workflows on stage

| | |
|---|---|
| Status | Accepted |
| Owner | Ujjwal Pardeshi |
| Date | 2026-10-02 |
| Related | [SPEC §14.5, §15, §24.5](../../SPEC.md) · [Architecture, section 5 (workflows)](../../ARCHITECTURE.md) · [System architecture §2.3](../system-architecture.md) · [DEMO.md (workflows: in-process or n8n)](../../DEMO.md) · [Demo runbook](../../06-delivery/demo-runbook.md) · [fs-08 console (provider panel)](../../02-product/feature-specs/fs-08-claims-officer-console.md) · [fs-03 EDI holiday (X4 renames a step)](../../02-product/feature-specs/fs-03-edi-holiday.md) · [Free-tier stack and setup](../free-tier-stack-and-setup.md) · [ADR 0001](0001-policy-engine-is-the-only-payout-authority.md) |

## TL;DR

Both workflow engines are BUILT and give the **same simulated timeline**: decisions at 17:00, credits, WhatsApp and Soundbox at 17:04, the instalment step at 17:05. On stage the default is the **in-process runner** (`make dev`, or `make up` with `CHHATRI_STACK_N8N_URL=` in `.env`). The console badge for n8n then reads SIMULATED. With `N8N_BASE_URL` set (`make up` does this unless it is emptied) the same three workflows run on n8n and the badge reads LIVE.

With n8n LIVE the replay clock holds at 17:00 for about 30 to 60 seconds of real time while the monsoon's 312 payout runs go through n8n (measured on an 8-CPU development machine, not yet on the demo laptop). That hold is why the stage default is in-process. n8n only orders the steps. It never decides and it never sets the timing.

## Context

**The workflows** (`backend/chhatri/workflows/definitions.py`). Offsets are simulated minutes from the decision.

| Workflow | Steps (offset) | Payload |
|---|---|---|
| `payout` | `execute_payout` +0, `credit_payout` +4, `notify_merchant` +4, `pause_instalment` +5 | `{decision_id, merchant_id}` |
| `human-review` | `open_case` +0, `notify_officer` +0 | `{case_id, merchant_id}` |
| `follow-up` | `check_case_sla` +24 h, `notify_officer` +24 h | `{case_id}` |

A run id is `{workflow}:{decision_id or case_id}`, so there is one run per subject, and a repeated start is ignored.

**Constraints that shaped the decision.**

1. **The clock is simulated.** The replay runs at a default of 6 simulated minutes per real second (range 1 to 120). A step must be due at a simulated time, never at a wall-clock time, or the replay and the audit chain would depend on machine speed.
2. **Determinism.** The same seed must give the same timings, ids and audit hashes.
3. **Stage conditions.** The on-site network is best effort, and the demo laptop would also have to run Docker for n8n.
4. **Honest labels.** The console says what is running: n8n is LIVE only when an n8n instance is configured.

## Decision

1. **Two engines behind one `WorkflowEngine` interface** (`backend/chhatri/integrations/base.py`):
   - `InProcessWorkflowEngine` (`backend/chhatri/workflows/runner.py`) schedules every step on the simulated scheduler at start + offset.
   - `N8nWorkflowEngine` (`backend/chhatri/integrations/n8n.py`) hands the same workflow to n8n.

   `build_workflow_engine` in `backend/chhatri/integrations/registry.py` picks n8n when `N8N_BASE_URL` is set and the in-process runner otherwise. The statuses are "in-process workflow runner (same steps)" (SIMULATED) and "n8n workflows (payout, human-review, follow-up)" (LIVE).
2. **Stage default: in-process.** Start with `make dev`, or `make up` with an empty `CHHATRI_STACK_N8N_URL=` in `.env`. Choosing n8n LIVE is a conscious choice made before the talk (DEMO.md).
3. **Same timeline in both modes.** With n8n, the backend POSTs `{N8N_BASE_URL}/webhook/chhatri-{workflow}` with the header `X-Chhatri-Secret`. n8n calls back `POST /internal/workflows/{step}` for each step in order. The backend schedules each effect at decision time + offset on the simulated scheduler, once per run and step. n8n answers the webhook from its last node, and the start call waits for that answer. So every step is already on the scheduler before the clock can pass its due minute. The generated workflows contain no Wait nodes.
4. **n8n never decides.** A callback is validated (`backend/chhatri/workflows/callbacks.py`, route in `backend/chhatri/api/routers/internal.py`) and the orchestrator re-validates the run (the run id matches the payload, the decision exists, is APPROVED and belongs to that merchant; a step already scheduled is skipped). The policy engine stays the only payout authority (ADR 0001).
5. **The n8n files are generated.** `n8n/workflows/*.json` come from `WORKFLOWS` through `scripts/n8n_workflows.py` (`make n8n-workflows`). `make test-infra` fails when they drift. `make n8n-selftest` runs the pinned image `docker.n8n.io/n8nio/n8n:2.41.3` against a stub backend and needs Docker.
6. **Failure handling.**

   | Event | What happens |
   |---|---|
   | n8n cannot be reached, answers non-2xx, or answers 2xx without the completion body | The run is handed to the in-process engine, which schedules only the steps n8n has not already reported. Logged at ERROR. The start is not retried, because n8n has already tried each callback three times. |
   | The start call times out (30 s) | Not handed over, because n8n may still be running the workflow and a second run could notify twice. Audited as `workflow.start_failed` and shown in the feed. The claims around it continue. |
   | A step fails, in either engine | The scheduler logs it, audits `workflow.step_failed`, adds a feed item and runs the next job. The replay continues. No step is retried automatically. |
   | A start repeats | Ignored (`accepted` is false, "already started"). |
7. **X4 renames one step.** `pause_instalment` becomes `request_holiday` ([fs-03](../../02-product/feature-specs/fs-03-edi-holiday.md), ADR 0006). The offset stays +5, so the timeline does not move. Both engines and the generated JSON change in one commit.
8. **X6 can switch n8n off at the panel.** While n8n is LIVE, the provider panel can force the next workflow runs to the in-process runner (`simulated`, the `n8n` row in fs-08 section 9).

## Alternatives considered

1. **n8n LIVE as the stage default (rejected, still available).** It shows the orchestration for real. The cost is the 30 to 60 second hold at 17:00, which is the moment the product is meant to show, plus a Docker container, a shared secret and a second process on the demo laptop. It stays one setting away (`make up` without emptying `CHHATRI_STACK_N8N_URL`).
2. **No workflow layer, orchestration inline in the handlers (rejected).** There would be no named steps, no shared step table, and nothing to generate the n8n files from. Two engines could not be compared.
3. **n8n only, no in-process runner (rejected).** `make dev`, the tests and `make demo-check` would all need Docker, and an n8n outage would stop payouts on stage.
4. **Batching payouts through n8n (not built).** n8n does not batch. Each shop's decision starts one `payout` run. The hold described in the TL;DR is the cost of 312 runs started one after another (each costs n8n about 0.1 to 0.2 seconds of real time), not a settlement window.

## Consequences

**Positive**

- No external dependency on stage: the demo runs offline with the in-process runner. With n8n on, a stopped or refusing n8n does not stop a payout, because the run falls back to the in-process runner. A hung n8n is the exception: its start times out after 30 seconds, is audited and is not handed over (decision 6).
- Same golden numbers and same timeline in both modes, tested (`test_n8n_callbacks_replay_the_in_process_timeline_exactly`).
- A judge can switch to n8n LIVE and see the executions list, and the badge says which engine ran.
- One step table (`WORKFLOWS`) drives both engines and the generated JSON, so there is one place to change a step.

**Negative**

- With the stage default, the n8n integration is demonstrated only when someone starts it. The badge says SIMULATED, and nothing simulated may be called live.
- Two engines to keep in step. The shared step table, the generated files and the tests carry that load.
- No step is retried automatically. A failed step shows in the feed and the audit chain and the replay goes on.

**Risks**

- **Engine divergence.** Mitigated by the single `WORKFLOWS` table, the drift check in `make test-infra` and the timeline test above.
- **The hold on the demo laptop is unknown.** The 30 to 60 seconds comes from one development machine. Rehearse n8n LIVE on the demo laptop before choosing it.
- **Version drift of n8n.** The compose file pins 2.41.3, and `make n8n-selftest` runs exactly that image.
- **Wording drift.** A page that calls n8n "the production orchestration" or "LIVE on stage" contradicts this ADR. What exists is an optional n8n service in the Docker stack, and whether a production deployment would use it is open.

## How we will know it was right

1. `make demo-check` passes in-process (70 checks, about 10 seconds), and `backend/scripts/demo_check.py --url` passes against the compose stack in both modes (about 50 seconds with n8n, per DEMO.md).
2. `test_monsoon_timeline_decision_1700_credit_1704_pause_1705` (`backend/tests/workflows/test_runner.py`) passes, and so does `test_n8n_callbacks_replay_the_in_process_timeline_exactly` (`backend/tests/replay/test_workflows.py`).
3. `test_unreachable_or_rejecting_n8n_falls_back_in_process`, `test_partial_run_hands_over_only_unreported_steps` and `test_without_fallback_errors_surface_and_timeouts_never_fall_back` (`backend/tests/integrations/test_n8n.py`) pass.
4. `make test-infra` is green: the generated JSON matches `WORKFLOWS`.
5. `test_a_workflow_engine_outage_is_audited_and_does_not_stop_the_claims` (`backend/tests/replay/test_workflows.py`) passes, and the audit chain shows `workflow.start_failed` and `workflow.step_failed` when something breaks.
6. The console header reads SIMULATED for n8n with the in-process runner and LIVE with n8n.

## Follow-ups

- Wave 1: rename `pause_instalment` to `request_holiday` with X4, and run `make n8n-workflows` and `make test-infra`.
- Wave 2: the `n8n` row of the provider panel (X6).
- Before the final: rehearse both modes on the demo laptop, note the real hold in the [demo runbook](../../06-delivery/demo-runbook.md) and decide.
- Keep the ADR index row for 0008, the free-tier page and SPEC §14.5 in line with this ADR. SPEC §14.5 describes a Wait node in `follow-up`, and the generated workflows have no Wait nodes.

## Open questions

1. Should the rehearsal slot show n8n LIVE (the executions list), and the timed demo switch to the in-process runner? Owner: Ujjwal Pardeshi.
2. Should a failed step retry once, idempotently, before it shows as failed? Today none does. Owner: Ujjwal Pardeshi.
3. Could the backend start the 312 payout runs concurrently to shorten the n8n hold? It was not tried, and concurrency would need the audit order to stay deterministic. Owner: Ujjwal Pardeshi.

## Changelog

- 2026-10-02 · v3 · rewritten against the code: both engines BUILT with one timeline; stage default in-process (`make dev`, or `make up` with `CHHATRI_STACK_N8N_URL=`) and the n8n badge SIMULATED unless `N8N_BASE_URL` is set; the `engine.py` snippet, the four workflows that do not exist, the retry logic and the "n8n batches payouts" explanation removed (the hold is the cost of 312 sequential runs, measured on a development machine); failure-handling table, real file paths and tests added; X4 step rename and the X6 `n8n` row noted; SPEC and architecture references corrected
- 2026-10-02 · v2 · final consistency pass against the code: no changes needed; ADR correctly describes in-process workflows as demo default with n8n as production path.
- 2026-10-02 · v1 · first draft.
