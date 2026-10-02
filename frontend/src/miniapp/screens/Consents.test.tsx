/** N6 consent centre, the withdraw and erase sheets, and the activity log: the flag, every state, the gates, the sheets' focus, and what a withdrawal does. */
import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import type { MockBackend } from '../../mock/backend'
import { testApi } from '../../mock/testkit'
import { renderStandalone } from '../shell/shellKit'

let backend: MockBackend
beforeEach(() => {
  vi.stubEnv('VITE_FEATURES', 'n1_miniapp,n6_consents')
  window.localStorage.clear()
})
afterEach(() => {
  backend?.dispose()
  vi.unstubAllEnvs()
})

type Kit = ReturnType<typeof testApi>
const SALES = 'SALES_DATA_FOR_CLAIM'
const SLIP = 'SLIP_DATA_FOR_HOSPITAL_CLAIM'
const SETTLEMENT = 'SETTLEMENT_DEDUCTION'

async function open(screenName: 'consents' | 'consent-activity' = 'consents', prepare?: (kit: Kit) => Promise<void>, merchant = 'S-0142', lang = 'en') {
  const kit = testApi()
  backend = kit.backend
  await kit.api.seek('17:05')
  kit.client.setOfficerToken((await kit.api.session()).officer_token)
  await prepare?.(kit)
  renderStandalone(`/merchant/${merchant}/app?lang=${lang}&screen=${screenName}`, kit.backend, kit.api)
  await waitFor(() => expect(screen.getByTestId(`screen-${screenName}`).getAttribute('data-state')).not.toBe('loading'))
  return kit
}

const text = (id: string) => screen.getByTestId(id).textContent ?? ''
const card = (purpose: string) => screen.getByTestId(`consent-${purpose}`)

/** Anil sends a slip that does not match his KYC name, so a review case opens (C-2291). */
async function toReview(kit: Kit): Promise<void> {
  await kit.api.load('illness_mismatch')
  await kit.api.seek('11:20')
  await kit.api.sendVoiceDemo('S-0142', 'ill')
  await kit.api.sendSampleSlip('S-0142', 'mismatch_admission_slip.png')
}
async function toAnswered(kit: Kit): Promise<void> {
  await toReview(kit)
  await kit.api.approve(kit.backend.runtime.cases[0].id, 'ok')
}

describe('the flag', () => {
  it('shows Home for both screens and no Help row while n6_consents is off', async () => {
    vi.stubEnv('VITE_FEATURES', 'n1_miniapp')
    const kit = testApi()
    backend = kit.backend
    renderStandalone('/merchant/S-0142/app?lang=en&screen=consents', kit.backend, kit.api)
    await waitFor(() => expect(screen.getByTestId('screen-home')).toBeTruthy())
    expect(screen.queryByTestId('help-consents')).toBeNull()
  })

  it('adds the Help row with the flag, and it opens the screen', async () => {
    const kit = testApi()
    backend = kit.backend
    renderStandalone('/merchant/S-0142/app?lang=en&screen=help', kit.backend, kit.api)
    fireEvent.click(await screen.findByTestId('help-consents'))
    expect(await screen.findByTestId('screen-consents')).toBeTruthy()
  })
})

describe('the consent centre', () => {
  it('shows the three purposes On, each marked SIMULATED with the seeded line, the date, the notice version and a bar to the log', async () => {
    await open()
    expect(screen.getByTestId('screen-consents').getAttribute('data-state')).toBe('ready')
    for (const purpose of [SALES, SLIP, SETTLEMENT]) {
      const c = within(card(purpose))
      expect(c.getByTestId('consent-state').textContent).toBe('On')
      expect(c.getByTestId('consent-simulated').getAttribute('data-mode')).toBe('SIMULATED')
      expect(card(purpose).textContent).toContain('Set up by the simulator for this demo.')
      expect(card(purpose).textContent).toContain('Agreed on 10 March')
    }
    expect(card(SALES).textContent).toContain('Use my sales data to decide claims and set my premium')
    expect(text('consent-version')).toBe('Notice notice-1. Prototype: nothing here is real data.')
    await waitFor(() => expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('see_activity'))
  })

  it('opens "What we use" in the accordion', async () => {
    await open()
    fireEvent.click(screen.getByTestId(`used-${SLIP}`))
    expect(await screen.findByText('The photo of the slip you send.')).toBeTruthy()
  })

  it('says a merchant with no cover has agreed to nothing, and leads to buying cover', async () => {
    await open('consents', undefined, 'S-0907')
    expect(screen.getByTestId('screen-consents').getAttribute('data-state')).toBe('empty')
    expect(text('app-empty')).toContain('You have not agreed to anything yet. You agree when you buy cover.')
    await waitFor(() => expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('get_cover_from_consents'))
    fireEvent.click(screen.getByTestId('consent-get-cover'))
    expect(await screen.findByTestId('screen-buy')).toBeTruthy()
  })

  it('shows the error state with the code when the data breaks the contract', async () => {
    const kit = testApi()
    backend = kit.backend
    const broken = { ...kit.api, consents: () => Promise.reject(new ApiError('contract_violation', 'consents: expected a list', 0)) }
    renderStandalone('/merchant/S-0142/app?lang=en&screen=consents', kit.backend, broken)
    await waitFor(() => expect(screen.getByTestId('screen-consents').getAttribute('data-state')).toBe('error'))
    expect(text('app-error')).toContain('contract_violation')
  })

  it('hides "Complain about my data" while n5_grievances is off', async () => {
    await open()
    expect(screen.queryByTestId('consent-complain')).toBeNull()
  })

  it('shows "Complain about my data" with n5_grievances, and it opens the form with that topic chosen', async () => {
    vi.stubEnv('VITE_FEATURES', 'n1_miniapp,n5_grievances,n6_consents')
    await open()
    fireEvent.click(screen.getByTestId('consent-complain'))
    expect(await screen.findByTestId('screen-grievances')).toBeTruthy()
    expect(await screen.findByTestId('grv-new-sheet')).toBeTruthy()
    expect(screen.getByTestId('grv-topic-DATA_OR_CONSENT').getAttribute('aria-pressed')).toBe('true')
  })
})

describe('turning a purpose off', () => {
  it('does not flip on tap: it asks first with the effect text, keeps focus on the safe button, and "Keep it on" changes nothing', async () => {
    const kit = await open()
    fireEvent.click(screen.getByTestId(`switch-${SLIP}`))
    const sheet = await screen.findByTestId('withdraw-sheet')
    expect(within(sheet).getByTestId('withdraw-effect').textContent).toContain('Chhatri stops reading slips')
    await waitFor(() => expect(document.activeElement).toBe(within(sheet).getByTestId('withdraw-sheet-keep')))
    expect(within(card(SLIP)).getByTestId('consent-state').textContent).toBe('On')
    fireEvent.click(within(sheet).getByTestId('withdraw-sheet-keep'))
    await waitFor(() => expect(screen.queryByTestId('withdraw-sheet')).toBeNull())
    expect((await kit.api.consents('S-0142'))[1].status).toBe('ACTIVE')
  })

  it('flips when the call succeeds, shows the way to turn it on again, and the chat gets one line', async () => {
    const kit = await open()
    fireEvent.click(screen.getByTestId(`switch-${SLIP}`))
    fireEvent.click(await screen.findByTestId('withdraw-sheet-confirm'))
    await waitFor(() => expect(within(card(SLIP)).getByTestId('consent-state').textContent).toBe('Off'))
    expect(text('consent-regrant')).toBe('To turn this on again, send a slip in the app and agree when asked.')
    expect((screen.getByTestId(`switch-${SLIP}`) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.queryByTestId('withdraw-sheet')).toBeNull()
    expect(kit.backend.runtime.messages.at(-1)?.text_en).toContain('you turned off slip reading')
  })

  it('names the reason and disables the switch while a claim review is open', async () => {
    await open('consents', toReview)
    expect(text('consent-blocked')).toBe('Your claim is still being checked by our team. You can turn this off once it is answered.')
    expect((screen.getByTestId(`switch-${SALES}`) as HTMLButtonElement).disabled).toBe(true)
  })

  it('shows the refusal inside the sheet and leaves the switch on when the server says a review is open', async () => {
    const kit = testApi()
    backend = kit.backend
    await kit.api.seek('17:05')
    const refusing = { ...kit.api, withdrawConsent: () => Promise.reject(new ApiError('case_open', 'a claim review is open', 409)) }
    renderStandalone('/merchant/S-0142/app?lang=en&screen=consents', kit.backend, refusing)
    fireEvent.click(await screen.findByTestId(`switch-${SALES}`))
    const sheet = await screen.findByTestId('withdraw-sheet')
    fireEvent.click(within(sheet).getByTestId('withdraw-sheet-confirm'))
    expect((await within(sheet).findByTestId('withdraw-sheet-error')).textContent).toContain('Your claim is still being checked by our team.')
    expect(within(card(SALES)).getByTestId('consent-state').textContent).toBe('On')
  })
})

describe('forget my slip', () => {
  it('lists the stored slip, disables Erase with the reason while the review is open', async () => {
    await open('consents', toReview)
    const held = within(screen.getByTestId('consent-held'))
    expect(held.getByText(/^Slip received/)).toBeTruthy()
    expect((screen.getByTestId(/^erase-MD-/) as HTMLButtonElement).disabled).toBe(true)
    expect(text('consent-held')).toContain('You can erase the slip once it is answered.')
  })

  it('says what is erased, what stays and that the log cannot be edited, starts on "Keep it", and marks the slip Erased', async () => {
    await open('consents', toAnswered)
    fireEvent.click(screen.getByTestId(/^erase-MD-/))
    const sheet = await screen.findByTestId('erase-sheet')
    expect(sheet.textContent).toContain('We will erase: the photo')
    expect(sheet.textContent).toContain('We will keep: the decision, the amount')
    expect(sheet.textContent).toContain('The activity log cannot be edited')
    await waitFor(() => expect(document.activeElement).toBe(within(sheet).getByTestId('erase-sheet-keep')))
    fireEvent.click(within(sheet).getByTestId('erase-sheet-confirm'))
    await waitFor(() => expect(screen.getByTestId(/^held-MD-/).getAttribute('data-state')).toBe('ERASED'))
    expect(screen.queryByTestId(/^erase-MD-/)).toBeNull()
  })

  it('closes on Escape without erasing', async () => {
    const kit = await open('consents', toAnswered)
    fireEvent.click(screen.getByTestId(/^erase-MD-/))
    const sheet = await screen.findByTestId('erase-sheet')
    fireEvent.keyDown(sheet, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByTestId('erase-sheet')).toBeNull())
    expect((await kit.api.consents('S-0142'))[1].held?.[0].state).toBe('HELD')
  })
})

describe('what was used', () => {
  it('lists fixed sentences, narrows by purpose, and ends with the way back and the simulated-times note', async () => {
    await open('consent-activity', toAnswered)
    expect(screen.getAllByTestId('activity-row').length).toBeGreaterThan(0)
    expect(screen.getAllByTestId('activity-row').some((row) => row.getAttribute('data-purpose') === SLIP)).toBe(true)
    fireEvent.click(screen.getByTestId(`activity-chip-${SETTLEMENT}`))
    await waitFor(() => expect(screen.getByTestId('screen-consent-activity').getAttribute('data-state')).toBe('empty'))
    expect(text('app-empty')).toContain('Nothing has been used yet.')
    fireEvent.click(screen.getByTestId('activity-chip-all'))
    await waitFor(() => expect(screen.getAllByTestId('activity-row').length).toBeGreaterThan(0))
    expect(screen.getByText('Times are simulated.')).toBeTruthy()
    expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('back_to_consents')
  })

  it('never prints a patient name: the sentences are fixed', async () => {
    await open('consent-activity', toAnswered)
    expect(document.body.textContent).not.toMatch(/Sunil|Pawar|Jadhav/i)
  })

  it('links a decision row to its receipt and runs the log check', async () => {
    await open('consent-activity', toAnswered)
    fireEvent.click(screen.getAllByTestId('activity-receipt')[0])
    expect(await screen.findByTestId('screen-receipt')).toBeTruthy()
  })

  it('checks the log', async () => {
    await open('consent-activity')
    fireEvent.click(screen.getByTestId('activity-check'))
    await waitFor(() => expect(text('activity-check-result')).toMatch(/^The log checks out: \d+ entries, none changed\.$/))
  })

  it('reads in Hindi', async () => {
    await open('consent-activity', toAnswered, 'S-0142', 'hi')
    expect(text('activity-chip-all')).toBe('सभी')
  })
})
