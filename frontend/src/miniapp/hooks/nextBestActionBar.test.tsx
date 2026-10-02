/** `useNextBest` runs the rules for a screen and registers the answer with the bar (fs-04 section 12, AC-36). */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useEffect, useState } from 'react'
import { MemoryRouter, useLocation } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ClaimItem, Cover } from '../../api/types'
import type { MockBackend } from '../../mock/backend'
import { testApi } from '../../mock/testkit'
import { LiveProvider } from '../../state/live'
import { MiniappProvider } from '../shell/MiniappContext'
import { NextBestBar } from '../shell/NextBestBar'
import { Probe } from '../shell/probe'
import { useNextBest, type NextBestArgs } from './nextBestActionBar'

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  window.localStorage.clear()
})
afterEach(() => backend?.dispose())

const COVER: Cover = {
  merchant_id: 'S-0142',
  cover_id: 'CV-0142',
  status: 'ACTIVE',
  status_text_hi: 'x',
  status_text_en: 'x',
  zone_id: 'Z7',
  zone_name: 'Parel',
  purchased_at: null,
  starts_on: '2025-03-17',
  prepaid_through: '2025-08-22',
  waiting_period_days: 7,
  premium_per_day_paise: 1862,
  premium_per_day_label: '₹18.62',
  premium_due: false,
  annual_limit_paise: 3_000_000,
  annual_limit_label: '₹30,000',
  amount_claimed_paise: 0,
  amount_claimed_label: '₹0',
  amount_remaining_paise: 3_000_000,
  amount_remaining_label: '₹30,000',
  alert_active: false,
  alert_id: null,
}
const PAID: ClaimItem = {
  claim_id: 'CL-000001',
  disputed_claim_id: null,
  kind: 'AREA',
  claim_at: '2025-08-19T17:00:00+05:30',
  zone_id: 'Z7',
  trigger_id: null,
  decision_id: 'D-000142',
  outcome: 'APPROVED',
  amount_paise: 138_000,
  amount_label: '₹1,380',
  steps: (['Detected', 'Checked', 'Decided', 'Paid', 'EDI holiday'] as const).map((name) => ({ name, status: 'completed' as const, result: null, at: null, reason_hi: null, reason_en: null, reason_code: null })),
  case_id: null,
  case_status: null,
  due_by: null,
  resolution: null,
}

function Hash() {
  return <output data-testid="hash">{useLocation().hash}</output>
}

function Harness({ args, late = false }: { args: NextBestArgs | null; late?: boolean }) {
  useNextBest(args)
  const [shown, setShown] = useState(!late)
  useEffect(() => {
    if (late) setTimeout(() => setShown(true), 50)
  }, [late])
  return <div>{shown ? <button type="button" data-testid="buy-check">check</button> : null}{shown ? <button type="button" data-testid="claim-dispute-button">dispute</button> : null}</div>
}

function mount(args: NextBestArgs | null, search = '?lang=en', late = false) {
  const kit = testApi()
  backend = kit.backend
  render(
    <MemoryRouter initialEntries={[`/merchant/S-0142/app${search}`]}>
      <LiveProvider api={kit.api} mock>
        <MiniappProvider merchantId="S-0142">
          <Harness args={args} late={late} />
          <NextBestBar />
        </MiniappProvider>
        <Probe />
        <Hash />
      </LiveProvider>
    </MemoryRouter>,
  )
  return kit
}

describe('useNextBest', () => {
  it('shows the sentence and the button of the rule that applies, with the rule id on the bar', async () => {
    mount({ screen: 'home', cover: COVER, claims: [PAID] })
    const bar = await screen.findByTestId('app-nba')
    expect(bar.getAttribute('data-nba')).toBe('see_why')
    expect(bar.textContent).toContain('Your payout of ₹1,380 was credited. See how it was worked out.')
    expect(screen.getByTestId('app-nba-action').textContent).toBe('Why this amount?')
    expect((screen.getByTestId('app-nba-action') as HTMLButtonElement).disabled).toBe(false)
  })

  it('speaks the language shown', async () => {
    mount({ screen: 'home', cover: COVER, claims: [PAID] }, '?lang=hi')
    const bar = await screen.findByTestId('app-nba')
    expect(bar.textContent).toContain('आपके ₹1,380 जमा हो गए हैं।')
    expect(screen.getByTestId('app-nba-action').textContent).toBe('इतने पैसे क्यों?')
  })

  it('draws no bar while the screen has nothing to say yet (loading or error)', async () => {
    mount(null)
    await waitFor(() => expect(screen.getByTestId('probe-location')).toBeTruthy())
    expect(screen.queryByTestId('app-nba')).toBeNull()
  })

  it('leads to the screen of the target, and keeps the language in the link', async () => {
    mount({ screen: 'home', cover: COVER, claims: [PAID] })
    fireEvent.click(await screen.findByTestId('app-nba-action'))
    await waitFor(() => expect(screen.getByTestId('probe-location').textContent).toBe('/merchant/S-0142/app?lang=en&screen=why&decision=D-000142'))
  })

  it('leads to a section of a screen through the hash', async () => {
    mount({ screen: 'home', cover: { ...COVER, premium_due: true }, claims: [] })
    fireEvent.click(await screen.findByTestId('app-nba-action'))
    await waitFor(() => expect(screen.getByTestId('hash').textContent).toBe('#c6'))
    expect(screen.getByTestId('probe-location').textContent).toBe('/merchant/S-0142/app?lang=en&screen=coverage')
  })

  it('moves focus to a control on this screen and moves nothing else', async () => {
    mount({ screen: 'buy', cover: { ...COVER, status: 'NONE', cover_id: null }, claims: [], buy: { phase: 'idle', simulated: true } })
    expect((await screen.findByTestId('app-nba')).getAttribute('data-nba')).toBe('check_price')
    fireEvent.click(screen.getByTestId('app-nba-action'))
    expect(document.activeElement).toBe(screen.getByTestId('buy-check'))
    expect(screen.getByTestId('probe-location').textContent).toBe('/merchant/S-0142/app?lang=en')
  })

  it('focuses the control of the screen it leads to once that screen has drawn it', async () => {
    mount({ screen: 'receipt', cover: COVER, claims: [PAID], claim: PAID }, '?lang=en&screen=receipt&decision=D-000142', true)
    const bar = await screen.findByTestId('app-nba')
    expect(bar.getAttribute('data-nba')).toBe('disagree')
    fireEvent.click(screen.getByTestId('app-nba-action'))
    await waitFor(() => expect(document.activeElement).toBe(screen.getByTestId('claim-dispute-button')))
  })

  it('disables the button offline and says why', async () => {
    vi.spyOn(window.navigator, 'onLine', 'get').mockReturnValue(false)
    mount({ screen: 'home', cover: COVER, claims: [PAID] })
    const action = (await screen.findByTestId('app-nba-action')) as HTMLButtonElement
    expect(action.disabled).toBe(true)
    expect(screen.getByTestId('app-nba').textContent).toContain('This needs the internet.')
  })
})
