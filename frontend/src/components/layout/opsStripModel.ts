/**
 * The words of the H8 ops strip (fs-08 10.1), as pure functions of the ops summary and the replay clock. Nothing here
 * invents a number: every figure is a field of GET /api/ops/summary, and the countdown is the browser's subtraction of
 * the case's `due_by` from the clock in the snapshot (fs-08 10.4), so the strip needs no polling.
 */
import type { CaseKind } from '../../api/types'
import type { OpsHolidayCounts, OpsSummary } from '../../api/opsWhatIf'
import { slaState } from '../../lib/time'

const KIND_WORDS: Readonly<Record<CaseKind, readonly [string, string]>> = {
  PERSONAL_CLAIM_REVIEW: ['claim review', 'claim reviews'],
  DISPUTE: ['dispute', 'disputes'],
  AREA_REVIEW: ['area review', 'area reviews'],
}
const KIND_ORDER: readonly CaseKind[] = ['PERSONAL_CLAIM_REVIEW', 'DISPUTE', 'AREA_REVIEW']

export const plural = (n: number, one: string, many: string = `${one}s`): string => `${n} ${n === 1 ? one : many}`

/** "1 dispute", "2 claim reviews, 1 dispute"; "none open" when nothing is. */
export function kindsLine(kinds: OpsSummary['cases_by_kind']): string {
  const parts = KIND_ORDER.filter((kind) => kinds[kind] > 0).map((kind) => `${kinds[kind]} ${KIND_WORDS[kind][kinds[kind] === 1 ? 0 : 1]}`)
  return parts.length === 0 ? 'none open' : parts.join(', ')
}

export type NextDue = { text: string; tone: 'ok' | 'warn' | 'overdue'; toneWord: string; caseId: string } | null

const TONE_WORDS = { ok: 'on time', warn: 'due soon', overdue: 'overdue' } as const

/** "C-2291 · 23 h 54 min left", or "C-2291 · overdue 1 h 5 min", with the tone in words. Null when nothing is open. */
export function nextDue(summary: OpsSummary, nowIso: string): NextDue {
  const next = summary.next_due_case
  if (!next) return null
  const sla = slaState(next.due_by, nowIso)
  return { text: `${next.id} · ${sla.label}`, tone: sla.tone, toneWord: TONE_WORDS[sla.tone], caseId: next.id }
}

export function engineLine(claims: OpsSummary['claims_today']): string {
  const total = claims.automatic + claims.human + claims.waiting
  return claims.automatic_share_pct === null ? 'No claims yet' : `${claims.automatic_share_pct}% · ${claims.automatic} of ${total}`
}

export function enginePopover(claims: OpsSummary['claims_today']): { label: string; value: number }[] {
  return [
    { label: 'Decided by the engine', value: claims.automatic },
    { label: 'Decided by an officer', value: claims.human },
    { label: 'Waiting for an officer', value: claims.waiting },
  ]
}

export function paidSub(pending: number): string | null {
  return pending > 0 ? `${pending} in flight` : null
}

/** Zones largest first, ties by zone id: the order of the paid popover. */
export function zoneRows(summary: OpsSummary): { zone: string; count: number; label: string }[] {
  return Object.entries(summary.payouts_today.by_zone)
    .toSorted(([za, a], [zb, b]) => b.paise - a.paise || za.localeCompare(zb, 'en', { numeric: true }))
    .map(([zone, row]) => ({ zone, count: row.count, label: row.label }))
}

/** "123 granted" and the other outcomes only when they are not zero. */
export function holidayLines(counts: OpsHolidayCounts): { main: string; others: string | null } {
  const others = [counts.REFUSED > 0 ? `${counts.REFUSED} refused` : null, counts.NO_RESPONSE > 0 ? `${counts.NO_RESPONSE} no answer` : null, counts.REQUESTED > 0 ? `${counts.REQUESTED} waiting` : null].filter((x): x is string => x !== null)
  return { main: `${counts.GRANTED} granted`, others: others.length > 0 ? others.join(', ') : null }
}

export function holidayPopover(counts: OpsHolidayCounts): { label: string; value: number }[] {
  return [
    { label: 'Granted', value: counts.GRANTED },
    { label: 'Refused', value: counts.REFUSED },
    { label: 'No answer from the lender', value: counts.NO_RESPONSE },
    { label: 'Waiting for the lender', value: counts.REQUESTED },
  ]
}
