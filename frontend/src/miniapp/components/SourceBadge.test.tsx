/** The source badge (H13, fs-04 10.3): what it says, what its sheet holds, focus, and "Source missing". */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Source } from '../../api/types'
import type { MockBackend } from '../../mock/backend'
import { testApi } from '../../mock/testkit'
import { LiveProvider } from '../../state/live'
import { MiniappProvider } from '../shell/MiniappContext'
import { clauseTitle, MissingSource, SourceBadge, SourceBadges, sourceLabel } from './SourceBadge'

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  window.localStorage.clear()
})
afterEach(() => {
  backend?.dispose()
  vi.restoreAllMocks()
})

const SALES: Source = { kind: 'SALES_INDEX', label: 'Zone sales index for the alert window', ref: 'trigger:E-Z7-20250819', as_of: '2025-08-19T17:00:00+05:30', origin: 'SIMULATED', clause: 'C2' }
const RULES: Source = { kind: 'RULES', label: 'Payout rules, pilot-0.1', ref: 'rules:pilot-0.1:payout_share', as_of: null, origin: 'CONFIG', clause: 'C4.1' }
const ALERT: Source = { kind: 'ALERT', label: 'IMD alert', ref: 'alert:A-20250818-01', as_of: '2025-08-18T17:30:00+05:30', origin: 'SIMULATED', clause: 'C2' }

function renderInApp(ui: React.ReactNode, search = '?lang=en') {
  const kit = testApi()
  backend = kit.backend
  return render(
    <MemoryRouter initialEntries={[`/merchant/S-0142/app${search}`]}>
      <LiveProvider api={kit.api} mock>
        <MiniappProvider merchantId="S-0142">{ui}</MiniappProvider>
      </LiveProvider>
    </MemoryRouter>,
  )
}

describe('the words on the badge', () => {
  it('names the kind, the rules version and the clause, and the origin word only where there is one', () => {
    renderInApp(<SourceBadges sources={[SALES, RULES]} rulesVersion="pilot-0.1" />)
    const [sales, rules] = screen.getAllByTestId('source-badge')
    expect(sales.textContent).toContain('Area sales index')
    expect(sales.textContent).toContain('17:00')
    expect(sales.textContent).toContain('SIMULATED')
    expect(rules.textContent).toContain('Chhatri rules pilot-0.1 · C4.1')
    expect(rules.textContent).not.toMatch(/SIMULATED|LIVE/)
  })

  it('says "Source", never that anyone verified or certified it', () => {
    renderInApp(<SourceBadges sources={[SALES, RULES, ALERT]} rulesVersion="pilot-0.1" />)
    expect(document.body.textContent).not.toMatch(/verified|certified/i)
    expect(screen.getAllByTestId('source-badge')[0].getAttribute('title')).toBe('Tap to see where this came from.')
  })

  it('reads the alert id from the reference and speaks Hindi in Hindi', () => {
    expect(sourceLabel(ALERT, 'en', 'pilot-0.1')).toBe('Weather alert A-20250818-01')
    expect(sourceLabel(ALERT, 'hi', 'pilot-0.1')).not.toBe(sourceLabel(ALERT, 'en', 'pilot-0.1'))
    expect(sourceLabel({ ...ALERT, ref: 'alert' }, 'en', 'pilot-0.1')).toBe('IMD alert')
  })

  it('names a clause by its parent clause', () => {
    expect(clauseTitle('C4.1', 'en')).toBe('How much we pay')
    expect(clauseTitle('C10', 'en')).toBe('Instalment holiday: your lender decides')
    expect(clauseTitle('C99', 'en')).toBeNull()
  })

  it('reads "Source missing" for a value with no source, in the blocked tone, with no badge', () => {
    renderInApp(<SourceBadges sources={[]} rulesVersion="pilot-0.1" testId="row-badges" />)
    expect(screen.getByTestId('source-missing').textContent).toBe('Source missing')
    expect(screen.queryByTestId('source-badge')).toBeNull()
    expect(screen.getByTestId('source-missing').className).toContain('text-blocked')
  })

  it('has a stand-alone "Source missing" in the language shown', () => {
    renderInApp(<MissingSource />, '?lang=hi')
    expect(screen.getByTestId('source-missing').textContent).not.toBe('Source missing')
  })
})

describe('the sheet', () => {
  it('holds the record, its time, the type of source and the clause, and puts the focus on Close', async () => {
    renderInApp(<SourceBadge source={SALES} rulesVersion="pilot-0.1" />)
    fireEvent.click(screen.getByTestId('source-badge'))
    const sheet = await screen.findByTestId('source-sheet')
    expect(sheet.textContent).toContain('Zone sales index for the alert window')
    expect(sheet.textContent).toContain('trigger:E-Z7-20250819')
    expect(sheet.textContent).toContain('19 August, 17:00')
    expect(screen.getByTestId('source-sheet-origin').textContent).toBe('SIMULATED')
    expect(sheet.textContent).toContain('C2')
    expect(sheet.textContent).toContain('Rain and lost sales')
    await waitFor(() => expect(document.activeElement).toBe(screen.getByTestId('source-sheet-close')))
  })

  it('closes with Escape and gives the focus back to the badge', async () => {
    renderInApp(<SourceBadge source={RULES} rulesVersion="pilot-0.1" />)
    const badge = screen.getByTestId('source-badge')
    fireEvent.click(badge)
    await screen.findByTestId('source-sheet')
    fireEvent.keyDown(document.activeElement ?? document.body, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByTestId('source-sheet')).toBeNull())
    await waitFor(() => expect(document.activeElement).toBe(badge))
  })

  it('closes with its Close button', async () => {
    renderInApp(<SourceBadge source={RULES} rulesVersion="pilot-0.1" />)
    fireEvent.click(screen.getByTestId('source-badge'))
    await screen.findByTestId('source-sheet')
    fireEvent.click(screen.getByTestId('source-sheet-close'))
    await waitFor(() => expect(screen.queryByTestId('source-sheet')).toBeNull())
  })
})
