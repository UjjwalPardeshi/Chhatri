/** N5 complaints and escalation: the flag, every state, opening, the ladder, escalating with a filing date, solving, and Hindi. */
import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import type { MockBackend } from '../../mock/backend'
import { testApi } from '../../mock/testkit'
import { renderStandalone } from '../shell/shellKit'

let backend: MockBackend
beforeEach(() => {
  vi.stubEnv('VITE_FEATURES', 'n1_miniapp,n5_grievances')
  window.localStorage.clear()
})
afterEach(() => {
  backend?.dispose()
  vi.unstubAllEnvs()
})

type Kit = ReturnType<typeof testApi>

async function open(search = '?lang=en&screen=grievances', prepare?: (kit: Kit) => Promise<void>, merchant = 'S-0142') {
  const kit = testApi()
  backend = kit.backend
  await kit.api.seek('17:05')
  kit.client.setOfficerToken((await kit.api.session()).officer_token)
  await prepare?.(kit)
  renderStandalone(`/merchant/${merchant}/app${search}`, kit.backend, kit.api)
  await waitFor(() => expect(screen.getByTestId('screen-grievances').getAttribute('data-state')).not.toBe('loading'))
  return kit
}

const text = (id: string) => screen.getByTestId(id).textContent ?? ''
const dispute = (kit: Kit) => kit.api.openGrievance('S-0142', { topic: 'PAYOUT_AMOUNT', text: 'मेरा नुकसान ज़्यादा हुआ।', lang: 'hi' }).then(() => undefined)
const answered = async (kit: Kit) => {
  await dispute(kit)
  const caseId = kit.backend.runtime.cases[0].id
  await kit.api.decline(caseId, 'the numbers stand')
}

describe('the flag', () => {
  it('shows Home for screen=grievances and no Help row while n5_grievances is off', async () => {
    vi.stubEnv('VITE_FEATURES', 'n1_miniapp')
    const kit = testApi()
    backend = kit.backend
    renderStandalone('/merchant/S-0142/app?lang=en&screen=grievances', kit.backend, kit.api)
    await waitFor(() => expect(screen.getByTestId('screen-home')).toBeTruthy())
    expect(screen.queryByTestId('screen-grievances')).toBeNull()
  })

  it('adds the Help row with the flag, and it opens the screen', async () => {
    const kit = testApi()
    backend = kit.backend
    renderStandalone('/merchant/S-0142/app?lang=en&screen=help', kit.backend, kit.api)
    fireEvent.click(await screen.findByTestId('help-grievances'))
    expect(await screen.findByTestId('screen-grievances')).toBeTruthy()
  })
})

describe('the states', () => {
  it('says there is nothing open and offers a new complaint, with a bar that does the same', async () => {
    await open()
    expect(screen.getByTestId('screen-grievances').getAttribute('data-state')).toBe('empty')
    expect(text('app-empty')).toContain('You have no open questions or complaints.')
    expect(screen.getByTestId('grv-new')).toBeTruthy()
    await waitFor(() => expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('grievances_new'))
  })

  it('shows the error state with Retry and the code when the data breaks the contract', async () => {
    const kit = testApi()
    backend = kit.backend
    const broken = { ...kit.api, grievances: () => Promise.reject(new ApiError('contract_violation', 'grievance: expected an object', 0)) }
    renderStandalone('/merchant/S-0142/app?lang=en&screen=grievances', kit.backend, broken)
    await waitFor(() => expect(screen.getByTestId('screen-grievances').getAttribute('data-state')).toBe('error'))
    expect(text('app-error')).toContain('contract_violation')
    expect(screen.getByTestId('app-error-retry')).toBeTruthy()
  })
})

describe('a new complaint', () => {
  it('keeps Send disabled until a topic and some words are given, names who answers, and never makes a second case', async () => {
    const kit = await open()
    fireEvent.click(screen.getByTestId('grv-new'))
    const send = await screen.findByTestId('grv-send')
    expect((send as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(screen.getByTestId('grv-topic-PAYOUT_AMOUNT'))
    expect(text('grv-who')).toBe('This goes to the insurer. Our claims officer looks first.')
    expect((screen.getByTestId('grv-send') as HTMLButtonElement).disabled).toBe(true)
    fireEvent.change(screen.getByTestId('grv-text'), { target: { value: 'My loss was bigger' } })
    expect((screen.getByTestId('grv-send') as HTMLButtonElement).disabled).toBe(false)
    fireEvent.click(screen.getByTestId('grv-send'))
    fireEvent.click(screen.getByTestId('grv-send'))
    await waitFor(() => expect(screen.getAllByTestId('grv-card')).toHaveLength(1))
    expect(kit.backend.runtime.cases.filter((c) => c.kind === 'DISPUTE')).toHaveLength(1)
    expect(screen.queryByTestId('grv-new-sheet')).toBeNull()
  })

  it('says the lender answers an instalment complaint, with one step and no case', async () => {
    await open()
    fireEvent.click(screen.getByTestId('grv-new'))
    fireEvent.click(await screen.findByTestId('grv-topic-EDI_HOLIDAY'))
    expect(text('grv-who')).toBe('This goes to your lender.')
    fireEvent.change(screen.getByTestId('grv-text'), { target: { value: 'My instalment was taken' } })
    fireEvent.click(screen.getByTestId('grv-send'))
    await waitFor(() => expect(screen.getByTestId('grv-step-LENDER_GRIEVANCE')).toBeTruthy())
    expect(screen.queryByTestId('grv-step-PAYTM_DISPUTE')).toBeNull()
    expect(text('grv-clock-LENDER_GRIEVANCE')).toBe('Response time to be confirmed with the lender.')
  })
})

describe('the ladder', () => {
  it('shows our claims officer with a clock, the other steps locked and marked SIMULATED or self-filed, and one line about the demo', async () => {
    await open('?lang=en&screen=grievances', dispute)
    const step = screen.getByTestId('grv-step-PAYTM_DISPUTE')
    expect(step.getAttribute('aria-current')).toBe('step')
    expect(text('grv-clock-PAYTM_DISPUTE')).toBe('We reply within 24 hours.')
    await waitFor(() => expect(text('grv-sentence-PAYTM_DISPUTE')).toBe('Our claims officer is looking at this. Answer due in 24 hours.'))
    expect(screen.getByTestId('grv-step-INSURER_GRO').getAttribute('data-state')).toBe('NOT_STARTED')
    expect(text('grv-state-INSURER_GRO')).toBe('Opens after the step before')
    expect(text('grv-delivery-INSURER_GRO')).toBe('SIMULATED in this demo. Nothing is sent.')
    expect(text('grv-delivery-BIMA_BHAROSA')).toBe('You file this yourself and tell us the date.')
    expect(text('grv-outside')).toContain('In this demo nothing is sent to them.')
    expect(text('grv-card')).toContain('Case C-2291')
    expect(screen.queryByTestId('grv-escalate-PAYTM_DISPUTE')).toBeNull()
    await waitFor(() => expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('grievances_open'))
    expect(text('app-nba')).toContain('You will hear back within 24 hours.')
  })

  it('offers the next step once the claims officer has answered, then asks for the filing date for the portal', async () => {
    await open('?lang=en&screen=grievances', answered)
    expect(text('grv-sentence-PAYTM_DISPUTE')).toContain('Answered: the decision stands.')
    fireEvent.click(screen.getByTestId('grv-escalate-PAYTM_DISPUTE'))
    await waitFor(() => expect(screen.getByTestId('grv-step-INSURER_GRO').getAttribute('aria-current')).toBe('step'))
    expect(text('grv-sentence-INSURER_GRO')).toContain('Sent to the insurer\'s grievance officer (SIMULATED in this demo).')
    expect(screen.getByTestId('grv-step-PAYTM_DISPUTE').getAttribute('data-state')).toBe('DONE')
    fireEvent.click(screen.getByTestId('grv-escalate-INSURER_GRO'))
    const sheet = await screen.findByTestId('grv-filing-sheet')
    expect(within(sheet).getByTestId('grv-bring').textContent).toMatch(/^Keep these ready: decision D-\d{6} and case C-2291\.$/)
    expect(sheet.textContent).toContain('bimabharosa.irdai.gov.in')
    fireEvent.change(within(sheet).getByTestId('grv-filed'), { target: { value: '2025-08-19' } })
    fireEvent.click(within(sheet).getByTestId('grv-save-date'))
    await waitFor(() => expect(screen.getByTestId('grv-step-BIMA_BHAROSA').getAttribute('aria-current')).toBe('step'))
    expect(text('grv-sentence-BIMA_BHAROSA')).toBe('You filed on 19 August. The portal says complaints are attended within 14 days. Day 1 of 14.')
    expect(screen.queryByTestId('grv-filing-sheet')).toBeNull()
  })

  it('opens the filing guide without a date field', async () => {
    await open('?lang=en&screen=grievances', async (kit) => {
      await answered(kit)
      const id = (await kit.api.grievances('S-0142'))[0].grievance_id
      await kit.api.escalateGrievance('S-0142', id, 'PAYTM_DISPUTE')
      await kit.api.escalateGrievance('S-0142', id, 'INSURER_GRO', '2025-08-19')
    })
    fireEvent.click(screen.getByTestId('grv-how'))
    const sheet = await screen.findByTestId('grv-filing-sheet')
    expect(within(sheet).queryByTestId('grv-filed')).toBeNull()
    expect(sheet.textContent).toContain('Contact details come from the partner. This is a placeholder in the demo.')
  })

  it('marks a complaint as solved and takes away its buttons', async () => {
    await open('?lang=en&screen=grievances', dispute)
    fireEvent.click(screen.getByTestId('grv-resolve-PAYTM_DISPUTE'))
    await waitFor(() => expect(screen.getByTestId('grv-card').getAttribute('data-status')).toBe('RESOLVED'))
    expect(screen.queryByTestId('grv-resolve-PAYTM_DISPUTE')).toBeNull()
  })

  it('reads in Hindi', async () => {
    await open('?lang=hi&screen=grievances', dispute)
    expect(text('grv-clock-PAYTM_DISPUTE')).toBe('हम 24 घंटे में जवाब देते हैं।')
    expect(text('grv-topic')).toBe('भुगतान की रकम')
  })
})
