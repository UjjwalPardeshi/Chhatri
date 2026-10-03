/**
 * Mock GET /api/evals/summary (H25, data-model 5.10; flag h25_evals, 404 `not_found` while it is off). The static demo
 * serves a copy of the stored run, `backend/artifacts/evals/summary.json` (`../data/evals-summary.json`; a test keeps
 * the two equal), so mock mode shows the same measured figures as the real backend and never an invented one.
 * Refresh it after a new run with: cp backend/artifacts/evals/summary.json frontend/src/mock/data/evals-summary.json
 */
import { isFeatureEnabled } from '../../features'
import { SUITE_IDS, type EvalsSummary } from '../../api/evals'
import storedRun from '../data/evals-summary.json'
import { notFound, ok, type Route } from '../http'

const NO_RUN_REASON = 'no run stored'

/** What the backend answers with no stored run: six suites in the plan's order, each NOT_MEASURED, no number. */
export const NO_RUN_SUMMARY: EvalsSummary = Object.freeze({
  measured: false,
  run: null,
  suites: SUITE_IDS.map((id) => ({ id, status: 'NOT_MEASURED' as const, reason: NO_RUN_REASON, metrics: [] })),
})

export const STORED_RUN: unknown = storedRun

export const EVALS_ROUTES: readonly Route[] = [
  {
    method: 'GET',
    pattern: /^\/api\/evals\/summary$/,
    handler: () => {
      if (!isFeatureEnabled('h25_evals')) throw notFound('route')
      return ok(STORED_RUN)
    },
  },
]
