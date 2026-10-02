/** The H8 ops strip (fs-08 10): cells from a fixture, overdue wording, popovers, the error state, and the flag. */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { OpsSummary } from '../../api/opsWhatIf'
import type { MockBackend } from '../../mock/backend'
import { testBackend } from '../../mock/testkit'
import { offlineTiles, renderApp } from '../../test/renderApp'
import { OpsStripView, type OpsStripViewProps } from './OpsStrip'
import { engineLine, holidayLines, kindsLine, nextDue, zoneRows } from './opsStripModel'

/** The monsoon replay at 17:06 after Anil's dispute, with X4 on (data-model 5.7). */
const SUMMARY: OpsSummary = {
  as_of: '2025-08-19T17:06:00+05:30',
  day: '2025-08-19',
  open_cases: 1,
  cases_by_kind: { PERSONAL_CLAIM_REVIEW: 0, DISPUTE: 1, AREA_REVIEW: 0 },
  overdue_cases: 0,
  next_due_case: { id: 'C-2291', kind: 'DISPUTE', merchant_id: 'S-0142', opened_at: '2025-08-19T17:06:00+05:30', due_by: '2025-08-20T17:00:00+05:30', due_in_minutes: 1434 },
  claims_today: { automatic: 312, human: 0, waiting: 0, automatic_share_pct: 100 },
  payouts_today: {
    credited_count: 312,
    credited_paise: 42_542_000,
    credited_label: '₹4,25,420',
    pending_count: 0,
    failed_count: 0,
    by_zone: {
      Z7: { count: 46, paise: 5_890_000, label: '₹58,900' },
      Z3: { count: 141, paise: 20_671_900, label: '₹2,06,719' },
      Z12: { count: 125, paise: 15_980_100, label: '₹1,59,801' },
    },
  },
  holiday_requests_today: { GRANTED: 123, REFUSED: 0, NO_RESPONSE: 0, REQUESTED: 0 },
}
const NOW = '2025-08-19T17:06:00+05:30'

const cell = (name: string) => screen.getByRole('button', { name: new RegExp(`^${name}`) })

function view(over: Partial<OpsStripViewProps> = {}) {
  const props: OpsStripViewProps = { summary: SUMMARY, error: false, loading: false, nowIso: NOW, onRetry: vi.fn<() => void>(), onNavigate: vi.fn<(to: string) => void>(), ...over }
  return { props, ...render(<OpsStripView {...props} />) }
}

describe('the words', () => {
  it('names the kinds, the countdown, the share, the zones and the holiday outcomes', () => {
    expect(kindsLine(SUMMARY.cases_by_kind)).toBe('1 dispute')
    expect(kindsLine({ PERSONAL_CLAIM_REVIEW: 2, DISPUTE: 1, AREA_REVIEW: 0 })).toBe('2 claim reviews, 1 dispute')
    expect(kindsLine({ PERSONAL_CLAIM_REVIEW: 0, DISPUTE: 0, AREA_REVIEW: 0 })).toBe('none open')
    expect(nextDue(SUMMARY, NOW)).toMatchObject({ text: 'C-2291 · 23 h 54 min left', toneWord: 'on time', caseId: 'C-2291' })
    expect(engineLine(SUMMARY.claims_today)).toBe('100% · 312 of 312')
    expect(engineLine({ automatic: 0, human: 0, waiting: 0, automatic_share_pct: null })).toBe('No claims yet')
    expect(zoneRows(SUMMARY).map((r) => r.zone)).toEqual(['Z3', 'Z12', 'Z7'])
    expect(holidayLines({ GRANTED: 123, REFUSED: 2, NO_RESPONSE: 1, REQUESTED: 0 })).toEqual({ main: '123 granted', others: '2 refused, 1 no answer' })
    expect(holidayLines(SUMMARY.holiday_requests_today as never).others).toBeNull()
  })

  it('says overdue in words and in the tone', () => {
    const late = { ...SUMMARY, overdue_cases: 1, next_due_case: { ...(SUMMARY.next_due_case as NonNullable<OpsSummary['next_due_case']>), due_by: '2025-08-19T16:01:00+05:30' } }
    expect(nextDue(late, NOW)).toMatchObject({ text: 'C-2291 · overdue 1 h 5 min', tone: 'overdue', toneWord: 'overdue' })
  })
})

describe('OpsStripView', () => {
  it('shows the five cells from the fixture', () => {
    view()
    expect(cell('Open cases').textContent).toContain('1 dispute')
    expect(cell('Next due').textContent).toContain('C-2291 · 23 h 54 min left')
    expect(cell('Next due').textContent).toContain('on time')
    expect(cell('Decided by the engine').textContent).toContain('100% · 312 of 312')
    expect(cell('Paid today').textContent).toContain('₹4,25,420 · 312 shops')
    expect(cell('Holiday requests').textContent).toContain('123 granted')
  })

  it('opens /claims and the due case from their cells', () => {
    const { props } = view()
    fireEvent.click(screen.getByRole('button', { name: /^Open cases/ }))
    expect(props.onNavigate).toHaveBeenLastCalledWith('/claims')
    fireEvent.click(screen.getByRole('button', { name: /^Next due/ }))
    expect(props.onNavigate).toHaveBeenLastCalledWith('/claims?case=C-2291')
  })

  it('opens the zone popover largest first, and Esc closes it', () => {
    view()
    fireEvent.click(screen.getByRole('button', { name: /^Paid today/ }))
    const pop = screen.getByRole('dialog', { name: 'Paid today by zone' })
    expect(within(pop).getAllByRole('term').map((t) => t.textContent)).toEqual(['Z3 · 141 shops', 'Z12 · 125 shops', 'Z7 · 46 shops'])
    expect(within(pop).getAllByRole('definition').map((d) => d.textContent)).toEqual(['₹2,06,719', '₹1,59,801', '₹58,900'])
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('opens the engine and holiday popovers with their counts', () => {
    view()
    fireEvent.click(screen.getByRole('button', { name: /^Decided by the engine/ }))
    expect(within(screen.getByRole('dialog')).getAllByRole('definition').map((d) => d.textContent)).toEqual(['312', '0', '0'])
    fireEvent.click(screen.getByRole('button', { name: /^Holiday requests/ }))
    expect(within(screen.getByRole('dialog', { name: 'Holiday requests today' })).getAllByRole('definition')).toHaveLength(4)
  })

  it('shows payouts in flight and hides the holiday cell while X4 is off', () => {
    const inFlight = { ...SUMMARY, holiday_requests_today: null, payouts_today: { ...SUMMARY.payouts_today, credited_count: 0, credited_paise: 0, credited_label: '₹0', by_zone: {}, pending_count: 312 } }
    view({ summary: inFlight })
    expect(screen.getByRole('button', { name: /^Paid today/ }).textContent).toContain('312 in flight')
    expect(screen.queryByRole('button', { name: /^Holiday requests/ })).toBeNull()
  })

  it('says it plainly when the numbers fail, with a Retry, and never shows old numbers', () => {
    const { props } = view({ summary: null, error: true })
    expect(screen.getByRole('alert').textContent).toBe('Ops numbers unavailable')
    expect(screen.queryByRole('button', { name: /^Open cases/ })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(props.onRetry).toHaveBeenCalledOnce()
  })

  it('says it is loading before the first numbers', () => {
    view({ summary: null, loading: true })
    expect(screen.getByText('Loading ops numbers…')).toBeTruthy()
  })

  it('has nothing to open when no case is due', () => {
    view({ summary: { ...SUMMARY, open_cases: 0, cases_by_kind: { PERSONAL_CLAIM_REVIEW: 0, DISPUTE: 0, AREA_REVIEW: 0 }, next_due_case: null } })
    expect((screen.getByRole('button', { name: /^Next due/ }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByRole('button', { name: /^Next due/ }).textContent).toContain('Nothing due')
  })
})

describe('in the console', () => {
  let backend: MockBackend
  beforeEach(() => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    offlineTiles()
    backend = testBackend()
  })
  afterEach(() => {
    backend.dispose()
    vi.unstubAllEnvs()
  })

  it('is not in the page while h8_ops_strip is off', async () => {
    renderApp('/live', backend)
    await screen.findByRole('button', { name: 'Play' })
    expect(document.querySelector('.ops-strip')).toBeNull()
  })

  it('is on /live and /claims with the flag, and not on the Overview or another page', async () => {
    vi.stubEnv('VITE_FEATURES', 'h8_ops_strip')
    renderApp('/live', backend)
    expect(await screen.findByRole('button', { name: /^Open cases/ })).toBeTruthy()
    expect(screen.getByRole('button', { name: /^Paid today/ }).textContent).toContain('₹0 · 0 shops')
  })

  it('is not on the audit page', async () => {
    vi.stubEnv('VITE_FEATURES', 'h8_ops_strip')
    renderApp('/audit', backend)
    await screen.findByRole('button', { name: 'Play' })
    await waitFor(() => expect(document.querySelector('.ops-strip')).toBeNull())
  })
})
