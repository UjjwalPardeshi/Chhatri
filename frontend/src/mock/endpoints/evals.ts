/**
 * Mock GET /api/evals/summary (H25, data-model 5.10; flag h25_evals, 404 `not_found` while it is off). The static demo
 * serves a copy of the stored `summary.json` when one is committed and the no-run response otherwise. None is
 * committed at build time (`backend/artifacts/evals/` does not exist), so this is the no-run response: six suites in
 * the plan's order, each NOT_MEASURED, with no number anywhere. It never holds an invented figure.
 */
import { isFeatureEnabled } from '../../features'
import { SUITE_IDS, type EvalsSummary } from '../../api/evals'
import { notFound, ok, type Route } from '../http'

const NO_RUN_REASON = 'no run stored'

export const NO_RUN_SUMMARY: EvalsSummary = Object.freeze({
  measured: false,
  run: null,
  suites: SUITE_IDS.map((id) => ({ id, status: 'NOT_MEASURED' as const, reason: NO_RUN_REASON, metrics: [] })),
})

export const EVALS_ROUTES: readonly Route[] = [
  {
    method: 'GET',
    pattern: /^\/api\/evals\/summary$/,
    handler: () => {
      if (!isFeatureEnabled('h25_evals')) throw notFound('route')
      return ok(NO_RUN_SUMMARY)
    },
  },
]
