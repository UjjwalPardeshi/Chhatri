/**
 * Mock GET /api/pricing (the pricing simulator, flag h24_whatif; data-model 5.9.1). The real route prices the levers
 * from the backend's pricing table (backend/artifacts/pricing/events.json), which the static demo does not carry, and
 * the mock never invents a price. So it answers in the real route's order: 404 `not_found` while the flag is off, 422
 * for a lever outside the route's bounds, then the 404 the real route gives with no table, so the Backtest page shows
 * its unavailable state.
 */
import { LEVER_KEYS, LEVER_QUERY, leverInRange } from '../../api/pricing'
import { isFeatureEnabled } from '../../features'
import { invalid, MockHttpError, notFound, type Route, type RouteContext } from '../http'

export const PRICING_ONLY_ON_BACKEND = 'the pricing table is only on the real backend; mock mode has no prices'

const WHOLE = /^-?\d+$/

/** Each lever in the query is a whole number inside the route's bounds; a lever left out takes the published rules. */
function checkLevers(query: URLSearchParams): void {
  for (const key of LEVER_KEYS) {
    const { param, min, max } = LEVER_QUERY[key]
    const raw = query.get(param)
    if (raw !== null && !(WHOLE.test(raw) && leverInRange(key, Number(raw)))) throw invalid(param, `a whole number from ${min} to ${max}`)
  }
}

function pricing(ctx: RouteContext): never {
  if (!isFeatureEnabled('h24_whatif')) throw notFound('route')
  checkLevers(ctx.query)
  throw new MockHttpError('not_found', PRICING_ONLY_ON_BACKEND, 404)
}

export const PRICING_ROUTES: readonly Route[] = [{ method: 'GET', pattern: /^\/api\/pricing$/, handler: pricing }]
