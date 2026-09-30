/**
 * Which case the Claims page shows (SPEC §20 "Claims", §17.1 scenario switches): the case in the
 * URL when this run's queue has it, otherwise the first case in the queue. Queue data is tagged
 * with the run it was loaded for, so after a scenario switch the page never asks for a case id
 * from the previous run (which would flash a NOT_FOUND error) while the new queue loads.
 */
import type { Case, CaseStatus, ClockState } from '../../api/types'

export type CaseFilter = CaseStatus | 'ALL'
export type RunCases = { run: string; filter: CaseFilter; cases: readonly Case[] }

/** Identifies one replay run: a scenario load starts a new one. */
export function runKey(clock: Pick<ClockState, 'scenario' | 'start'> | null | undefined): string | null {
  return clock ? `${clock.scenario}|${clock.start}` : null
}

/**
 * The case to show. `requested` is the ?case= id; it is dropped only when a full queue (filter
 * ALL) for this run does not contain it. A filtered queue can't rule a case out: an approved case
 * leaves the Open list but stays selected so its resolution stays on screen.
 */
export function pickCase(requested: string | null, list: RunCases | null, run: string | null): string | null {
  const fresh = list !== null && run !== null && list.run === run ? list : null
  if (fresh === null) return null
  const ruledOut = requested !== null && fresh.filter === 'ALL' && !fresh.cases.some((c) => c.id === requested)
  if (requested !== null && !ruledOut) return requested
  return fresh.cases[0]?.id ?? null
}

/** True when the URL names a case that this run's full queue does not have. */
export function isStaleRequest(requested: string | null, list: RunCases | null, run: string | null): boolean {
  return requested !== null && list !== null && list.run === run && pickCase(requested, list, run) !== requested
}

function rank(c: Case): number {
  return c.status === 'OPEN' ? 0 : 1
}

/** Open cases first, then the rest, newest first within each group. */
export function queueOrder(cases: readonly Case[]): Case[] {
  return cases.toSorted((a, b) => rank(a) - rank(b) || b.opened_at.localeCompare(a.opened_at))
}
