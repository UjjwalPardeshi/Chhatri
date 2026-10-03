/** S5 Claim detail (fs-04 section 8, H1): five steps, the case chip and the clock, the lender's answer, "This is wrong", what happens next (AC-17, AC-19 to AC-25). */
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiClient, ApiError } from '../../api/client'
import type { HolidayStatus, ReceiptEdi } from '../../api/types'
import type { MockBackend } from '../../mock/backend'
import {
  areaCreditPending,
  areaDeclined,
  areaLenderAsked,
  areaLenderRefused,
  areaNoLoan,
  disputeClosed,
  claim,
  personalOfficerApproved,
  personalReferred,
  personalOfficerDeclined,
  personalWaitingForSlip,
} from '../../test/claimFixtures'
import { referredSession, session, stubClaims, stubReceipt } from '../../test/claimScenes'
import { hi } from '../copy/hi'
import { DISPUTE_PHRASE } from './ClaimDetailDispute'
import { renderStandalone } from '../shell/shellKit'

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  window.localStorage.clear()
})
afterEach(() => {
  backend?.dispose()
  vi.restoreAllMocks()
})

const STEPS = ['detected', 'checked', 'decided', 'paid', 'edi'] as const
const text = (id: string) => screen.getByTestId(id).textContent ?? ''
const status = (id: string) => screen.getByTestId(`claim-step-${id}`).getAttribute('data-status')

async function openClaim(kit: { backend: MockBackend }, claimId = 'CL-000142', search = '?lang=en', state = 'ready') {
  backend = kit.backend
  const view = renderStandalone(`/merchant/S-0142/app?${search.replace(/^\?/, '')}&screen=claim&claim=${claimId}`, kit.backend)
  await waitFor(() => expect(screen.getByTestId('screen-claim').getAttribute('data-state')).toBe(state))
  return view
}

describe('an area claim (AC-17)', () => {
  it('shows five steps, all done, with the times 17:00, 17:00, 17:00, 17:04 and 17:05', async () => {
    await openClaim(await session('monsoon', '17:05'))
    expect(STEPS.map(status)).toEqual(['completed', 'completed', 'completed', 'completed', 'completed'])
    const times = STEPS.map((id) => screen.getByTestId(`claim-step-${id}`).querySelector('time')?.textContent)
    expect(times).toEqual(['17:00', '17:00', '17:00', '17:04', '17:05'])
    expect(text('claim-step-decided')).toContain('Approved ₹1,380')
    expect(text('claim-step-decided')).toContain('½ × ₹4,380 × 63% = ₹1,380')
    expect(text('claim-step-detected')).toContain("Your area's sales fell 63% during the alert.")
    expect(text('claim-step-checked')).toContain('All 9 checks passed.')
    expect(screen.getByTestId('claim-stepper').querySelector('[aria-current="step"]')).toBeNull()
  })

  it('carries the kind, the day, the pill and the amount in the header, and SIMULATED on the payout and the lender', async () => {
    await openClaim(await session('monsoon', '17:05'))
    expect(text('claim-kind')).toBe('Rain and lost sales')
    expect(text('claim-date')).toBe('19 August')
    expect(text('claim-pill')).toBe('Paid')
    expect(screen.getByTestId('claim-pill').getAttribute('data-status')).toBe('APPROVED')
    expect(text('claim-amount')).toBe('₹1,380')
    expect(within(screen.getByTestId('claim-step-paid')).getByText(/SIMULATED payment/)).toBeTruthy()
    expect(within(screen.getByTestId('claim-step-edi')).getByText(/SIMULATED lender/)).toBeTruthy()
    expect(within(screen.getByTestId('claim-step-detected')).queryByText(/SIMULATED/)).toBeNull()
  })

  it('is an ordered list of five steps with a polite live region that names the last step done', async () => {
    await openClaim(await session('monsoon', '17:05'))
    const list = screen.getByTestId('claim-stepper')
    expect(list.tagName).toBe('OL')
    expect(within(list).getAllByRole('listitem')).toHaveLength(5)
    const live = screen.getByTestId('claim-live')
    expect(live.getAttribute('aria-live')).toBe('polite')
    expect(live.textContent).toContain('Instalment holiday (EDI)')
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
  })

  it('links to the receipt of the decision and leaves the "Why this amount?" link to the next-step bar', async () => {
    await openClaim(await session('monsoon', '17:05'))
    expect(screen.getByTestId('claim-open-receipt').getAttribute('href')).toBe('/merchant/S-0142/app?lang=en&screen=receipt&decision=D-000142')
    expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('see_why')
    expect(screen.queryByTestId('claim-open-why')).toBeNull()
  })

  it('offers the link to Why in the body where the bar says something else, and "This is wrong" only on a paid claim', async () => {
    stubClaims([areaCreditPending()])
    await openClaim(await session('monsoon', '17:00'))
    expect(screen.getByTestId('app-nba').getAttribute('data-nba')).not.toBe('see_why')
    expect(screen.getByTestId('claim-open-why').getAttribute('href')).toBe('/merchant/S-0142/app?lang=en&screen=why&decision=D-000142')
    expect(screen.queryByTestId('claim-dispute-button')).toBeNull()
    expect(status('paid')).toBe('current')
    expect(screen.getByTestId('claim-step-paid').getAttribute('aria-current')).toBe('step')
    expect(text('claim-step-paid')).toContain('₹1,380 is on its way, with the next settlement.')
    expect(text('claim-step-paid')).toContain('Credit in about 4 minutes (demo clock).')
    expect(status('edi')).toBe('pending')
    expect(text('claim-live')).toContain('Paid')
  })

  it('says "We asked your lender" while the lender has not answered', async () => {
    stubClaims([areaLenderAsked()])
    await openClaim(await session('monsoon', '17:04'))
    expect(status('edi')).toBe('current')
    expect(text('claim-step-edi')).toContain('We asked your lender. The lender decides.')
    expect(text('claim-step-edi')).toContain('SIMULATED lender')
  })

  it('speaks Hindi by default and keeps the case chip words in English', async () => {
    await openClaim(await session('monsoon', '17:05'), 'CL-000142', '?')
    expect(text('claim-step-detected')).toContain('पता चला')
    expect(text('claim-step-detected')).toContain('अलर्ट के दौरान आपके इलाके की बिक्री 63% गिरी।')
    expect(text('claim-step-paid')).toContain('SIMULATED भुगतान')
    expect(text('claim-pill')).toBe('भुगतान हुआ')
  })
})

describe('a claim sent to a claims officer (AC-19)', () => {
  it('shows the case chip, the clock and the person step as current, and Paid and EDI holiday pending', async () => {
    await openClaim(await referredSession(), 'CL-000001')
    expect(status('decided')).toBe('current')
    expect(screen.getByTestId('claim-step-decided').getAttribute('aria-current')).toBe('step')
    expect(text('claim-step-decided')).toContain('With a claims officer')
    expect(text('claim-case-chip')).toBe('Sent to a claims officer · case C-2291')
    await waitFor(() => expect(text('claim-clock')).toBe('24 hours left'))
    expect(status('paid')).toBe('pending')
    expect(status('edi')).toBe('pending')
    expect(text('claim-pill')).toBe('With a claims officer')
    expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('wait_for_officer')
    expect(screen.queryByTestId('claim-dispute-button')).toBeNull()
    expect(screen.queryByTestId('claim-amount')).toBeNull()
  })

  it('keeps the chip in English in Hindi, marked as English, and words the clock in Hindi', async () => {
    await openClaim(await referredSession(), 'CL-000001', '?')
    const chip = screen.getByTestId('claim-case-chip')
    expect(chip.textContent).toBe('Sent to a claims officer · case C-2291')
    expect(chip.getAttribute('lang') ?? chip.querySelector('[lang]')?.getAttribute('lang')).toBe('en')
    await waitFor(() => expect(text('claim-clock')).toBe('24 घंटे बाकी'))
  })

  it('says the time limit has passed once the replay clock is beyond the due time', async () => {
    stubClaims([{ ...personalReferred(), due_by: '2025-08-20T11:20:00+05:30' }])
    await openClaim(await referredSession(), 'CL-000001')
    await waitFor(() => expect(text('claim-clock')).toBe('Past the time limit'))
  })
})

describe('an officer decides (AC-20, AC-21)', () => {
  it('shows "Approved by a claims officer" with the amount, and the credit as done', async () => {
    const kit = await referredSession()
    await kit.api.approve('C-2291', '')
    kit.backend.step(5)
    await openClaim(kit, 'CL-000001')
    expect(text('claim-step-decided')).toContain('Approved by a claims officer')
    expect(text('claim-step-decided')).toContain('₹1,500')
    expect(status('decided')).toBe('completed')
    expect(status('paid')).toBe('completed')
    expect(screen.queryByTestId('claim-case-chip')).toBeNull()
    expect(text('claim-pill')).toBe('Approved by a claims officer')
  })

  it('says the officer approved even before the credit is in, with the credit as the current step', async () => {
    stubClaims([personalOfficerApproved()])
    await openClaim(await referredSession(), 'CL-000001')
    expect(text('claim-step-decided')).toContain('Approved by a claims officer')
    expect(status('paid')).toBe('current')
    expect(text('claim-step-paid')).toContain('₹1,500 is on its way')
  })

  it('shows "Not paid" with the officer\'s reason, and skips Paid and the EDI holiday', async () => {
    stubClaims([personalOfficerDeclined()])
    await openClaim(await referredSession(), 'CL-000001')
    expect(status('decided')).toBe('completed')
    expect(screen.getByTestId('claim-step-decided').getAttribute('data-result')).toBe('DECLINED')
    expect(text('claim-step-decided')).toContain('Not paid')
    expect(text('claim-step-decided')).toContain("The name on the slip doesn't match your KYC, so this claim can't be approved.")
    expect(text('claim-step-decided')).toContain('Stopped here')
    expect(status('paid')).toBe('skipped')
    expect(status('edi')).toBe('skipped')
    expect(screen.queryByTestId('claim-dispute-button')).toBeNull()
    expect(text('claim-pill')).toBe('Not paid')
    expect(text('claim-step-paid')).toContain('Not needed')
  })

  it('does the same for a declined area claim, and offers the receipt but not "This is wrong"', async () => {
    stubClaims([areaDeclined()])
    await openClaim(await session('monsoon', '17:05'))
    expect([status('paid'), status('edi')]).toEqual(['skipped', 'skipped'])
    expect(screen.getByTestId('claim-open-receipt')).toBeTruthy()
    expect(screen.queryByTestId('claim-dispute-button')).toBeNull()
    expect(screen.queryByTestId('claim-amount')).toBeNull()
  })

  it('shows a hospital-cash claim that waits for the slip, with no receipt to open', async () => {
    stubClaims([personalWaitingForSlip()])
    await openClaim(await session('illness', '11:20'), 'CL-000001')
    expect(status('detected')).toBe('current')
    expect(text('claim-step-detected')).toContain('Waiting for your slip')
    expect(STEPS.slice(1).map(status)).toEqual(['pending', 'pending', 'pending', 'pending'])
    expect(screen.queryByTestId('claim-open-receipt')).toBeNull()
    expect(screen.queryByTestId('claim-open-why')).toBeNull()
  })
})

describe('"This is wrong" (AC-22)', () => {
  it('sends the dispute phrase through the messages route, thanks in a toast, and shows the question under the claim', async () => {
    const post = vi.spyOn(ApiClient.prototype, 'post')
    await openClaim(await session('monsoon', '17:12'))
    expect(text('claim-dispute-button')).toBe('This is wrong')
    fireEvent.click(screen.getByTestId('claim-dispute-button'))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/merchants/S-0142/messages', { text: DISPUTE_PHRASE }))
    expect(DISPUTE_PHRASE).toBe('मेरा नुकसान ज़्यादा हुआ।')
    await waitFor(() => expect(text('app-toast-host')).toContain("Okay, I'm sending this to our team. You'll hear back within 24 hours."))
    const card = await screen.findByTestId('claim-dispute-card')
    expect(card.textContent).toContain('Question open')
    expect(card.textContent).toContain('₹1,380')
    expect(text('claim-case-chip')).toBe('Sent to a claims officer · case C-2291')
    await waitFor(() => expect(text('claim-clock')).toBe('24 hours left'))
    expect(screen.queryByTestId('claim-dispute-button')).toBeNull()
    expect(text('claim-amount')).toBe('₹1,380')
    expect(text('claim-step-decided')).toContain('Approved ₹1,380')
    expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('wait_for_officer')
  })

  it('thanks in Hindi when the app is in Hindi', async () => {
    await openClaim(await session('monsoon', '17:12'), 'CL-000142', '?')
    fireEvent.click(screen.getByTestId('claim-dispute-button'))
    await waitFor(() => expect(text('app-toast-host')).toContain('ठीक है, मैं इसे हमारी टीम को भेज रहा हूँ। 24 घंटे में जवाब मिलेगा।'))
  })

  it('moves focus to the case chip once the question is open, so the button that went away does not drop the focus', async () => {
    await openClaim(await session('monsoon', '17:12'))
    fireEvent.click(screen.getByTestId('claim-dispute-button'))
    const chip = await screen.findByTestId('claim-case-chip')
    await waitFor(() => expect(document.activeElement).toBe(chip))
  })

  it('shows an error under the button and keeps it, when the message cannot be sent', async () => {
    const real = ApiClient.prototype.post
    vi.spyOn(ApiClient.prototype, 'post').mockImplementation(function (this: ApiClient, path: string, body?: unknown, auth?: boolean) {
      if (path.endsWith('/messages')) return Promise.reject(new ApiError('internal_error', 'boom', 500))
      return real.call(this, path, body, auth)
    })
    await openClaim(await session('monsoon', '17:12'))
    fireEvent.click(screen.getByTestId('claim-dispute-button'))
    await waitFor(() => expect(text('claim-dispute-error')).toContain('Something went wrong. Try again.'))
    expect((screen.getByTestId('claim-dispute-button') as HTMLButtonElement).disabled).toBe(false)
    expect(screen.getByTestId('claim-dispute-button').getAttribute('aria-busy')).toBeNull()
    expect(screen.queryByTestId('claim-dispute-card')).toBeNull()
  })

  it('is disabled with a reason while offline', async () => {
    await openClaim(await session('monsoon', '17:12'))
    vi.spyOn(window.navigator, 'onLine', 'get').mockReturnValue(false)
    act(() => void window.dispatchEvent(new Event('offline')))
    await waitFor(() => expect(screen.getByTestId('screen-claim').getAttribute('data-state')).toBe('offline'))
    expect((screen.getByTestId('claim-dispute-button') as HTMLButtonElement).disabled).toBe(true)
    expect(text('screen-claim')).toContain('This needs the internet. Please try again when you are online.')
  })

  it('is not offered while a question about this claim is open', async () => {
    const kit = await session('monsoon', '17:12')
    await kit.api.sendText('S-0142', DISPUTE_PHRASE)
    await openClaim(kit)
    expect(screen.queryByTestId('claim-dispute-button')).toBeNull()
    expect(text('claim-dispute-card')).toContain('Question open')
  })
})

describe('a question that is closed (AC-23)', () => {
  it.each([
    ['approves', 'Amount confirmed'],
    ['declines', 'The numbers support the amount paid.'],
  ])('keeps the amount at ₹1,380 and shows the note when the officer %s', async (verb, note) => {
    const kit = await session('monsoon', '17:12')
    await kit.api.sendText('S-0142', DISPUTE_PHRASE)
    await (verb === 'approves' ? kit.api.approve('C-2291', note) : kit.api.decline('C-2291', note))
    await openClaim(kit)
    const card = screen.getByTestId('claim-dispute-card')
    expect(card.textContent).toContain('Question closed. Amount unchanged.')
    expect(card.textContent).toContain('Our team checked it. The amount paid stays ₹1,380.')
    expect(within(card).getByTestId('claim-dispute-amount').textContent).toBe('₹1,380')
    expect(text('claim-resolution')).toContain(note)
    expect(text('claim-amount')).toBe('₹1,380')
    expect(screen.queryByTestId('claim-case-chip')).toBeNull()
    expect(screen.queryByTestId('claim-clock')).toBeNull()
    expect(card.textContent).not.toMatch(/new amount|increase|revised/i)
  })

  it('shows the closed card of a fixture with its note', async () => {
    stubClaims([disputeClosed(), claim()])
    await openClaim(await session('monsoon', '17:12'))
    expect(text('claim-resolution')).toContain('Amount confirmed')
    expect(text('claim-resolution')).toContain('Note from our team')
  })
})

describe("the lender's answer (AC-24, AC-25)", () => {
  it('shows the lender\'s own answer and never says Chhatri paused the instalment', async () => {
    await openClaim(await session('monsoon', '17:05'))
    expect(text('claim-step-edi')).toContain("Tomorrow's ₹600 instalment is paused.")
    expect(document.body.textContent).not.toMatch(/chhatri\s+(has\s+)?paused/i)
    expect(document.body.textContent).not.toMatch(/छतरी ने (किस्त )?रोक/)
  })

  it('reads "Not available" for a refusal and shows no reason code or reason', async () => {
    stubClaims([areaLenderRefused()])
    await openClaim(await session('monsoon', '17:05'))
    expect(status('edi')).toBe('completed')
    expect(screen.getByTestId('claim-step-edi').getAttribute('data-result')).toBe('REFUSED')
    expect(text('claim-step-edi')).toContain('Not available. Your instalment is due as usual.')
    expect(document.body.textContent).not.toContain('IN_ARREARS')
    expect(document.body.textContent).not.toMatch(/arrears|overdue/i)
    expect(document.body.textContent).not.toMatch(/chhatri\s+(has\s+)?paused/i)
  })

  it('skips the EDI holiday with "No loan on file" for a merchant with no loan', async () => {
    stubClaims([areaNoLoan()])
    await openClaim(await session('monsoon', '17:05'))
    expect(status('edi')).toBe('skipped')
    expect(text('claim-step-edi')).toContain('No loan on file')
    expect(text('claim-step-edi')).not.toContain('SIMULATED lender')
  })
})

/** The lender block of a receipt with this answer: a refusal carries its code (never shown), a request has no answer time. */
function lenderBlock(answer: HolidayStatus): ReceiptEdi {
  return {
    request_id: 'HR-000001',
    status: answer,
    reason_code: answer === 'REFUSED' ? 'IN_ARREARS' : null,
    instalment_date: '2025-08-20',
    instalment_label: '₹600',
    decided_at: answer === 'REQUESTED' ? null : '2025-08-19T17:05:00+05:30',
    lender: 'Demo Lender',
  }
}

const nextIds = () => within(screen.getByTestId('claim-next-steps')).getAllByRole('listitem').map((step) => step.getAttribute('data-step'))

describe('what happens next, once the payout is credited', () => {
  it('lists the money, what to do if the amount looks wrong and the cover, above the steps, from the receipt and the cover', async () => {
    const kit = await session('monsoon', '17:05')
    const receipt = await kit.api.receipt('D-000142')
    await openClaim(kit)
    const card = await screen.findByTestId('claim-next-steps')
    expect(within(card).getByRole('heading').textContent).toBe('What happens next')
    expect(card.compareDocumentPosition(screen.getByTestId('claim-stepper')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    await waitFor(() => expect(nextIds()).toEqual(['money', 'wrong', 'cover']))
    expect(text('claim-next-money')).toContain('₹1,380 was credited with your settlement on 19 August, 17:04.')
    expect(text('claim-next-money')).toContain('SIMULATED payment')
    expect(text('claim-next-wrong')).toContain('If the amount looks wrong, tap This is wrong.')
    expect(text('claim-next-wrong')).toContain(`We reply within ${receipt.grievance.first_step_hours} hours.`)
    expect(text('claim-next-cover')).toContain('Your cover continues. The premium is paid up to 22 August.')
  })

  it('has no lender step while the receipt has no lender block, though the instalment step has its own line', async () => {
    await openClaim(await session('monsoon', '17:05'))
    await screen.findByTestId('claim-next-money')
    expect(screen.queryByTestId('claim-next-lender')).toBeNull()
    expect(text('claim-step-edi')).toContain("Tomorrow's ₹600 instalment is paused.")
  })

  it.each([
    ['GRANTED', 'Your lender has paused the ₹600 instalment due on 20 August. It moves to the end of your loan with no penalty.'],
    ['REQUESTED', 'We asked your lender. The lender decides.'],
    ['REFUSED', 'Not available. Your instalment is due as usual.'],
    ['NO_RESPONSE', 'We could not reach your lender. Your instalment is due as usual.'],
  ] as const)('words the lender answer %s with the fixed line for it, after the money, and never says Chhatri paused it', async (answer, line) => {
    const kit = await session('monsoon', '17:05')
    const receipt = await kit.api.receipt('D-000142')
    stubReceipt({ ...receipt, edi: lenderBlock(answer) })
    await openClaim(kit)
    const lender = await screen.findByTestId('claim-next-lender')
    expect(lender.textContent).toContain(line)
    expect(lender.textContent).toContain('SIMULATED lender')
    expect(nextIds().slice(0, 2)).toEqual(['money', 'lender'])
    expect(document.body.textContent).not.toMatch(/chhatri\s+(has\s+)?paused/i)
    expect(document.body.textContent).not.toContain('IN_ARREARS')
  })

  it('leaves out "If the amount looks wrong" while a question about the payout is open', async () => {
    const kit = await session('monsoon', '17:12')
    await kit.api.sendText('S-0142', DISPUTE_PHRASE)
    await openClaim(kit)
    await screen.findByTestId('claim-next-money')
    expect(screen.getByTestId('claim-dispute-card')).toBeTruthy()
    expect(screen.queryByTestId('claim-next-wrong')).toBeNull()
  })

  it('holds its place while the receipt loads, and draws nothing when the receipt fails: the steps already say what happened', async () => {
    const real = ApiClient.prototype.get
    let answer: 'hang' | 'fail' = 'hang'
    vi.spyOn(ApiClient.prototype, 'get').mockImplementation(function (this: ApiClient, path: string, signal?: AbortSignal) {
      if (path.endsWith('/receipt')) return (answer === 'hang' ? new Promise(() => undefined) : Promise.reject(new ApiError('internal_error', 'boom', 500))) as never
      return real.call(this, path, signal)
    })
    const view = await openClaim(await session('monsoon', '17:05'))
    expect(await screen.findByTestId('claim-next-loading')).toBeTruthy()
    expect(screen.queryByTestId('claim-next-steps')).toBeNull()
    view.unmount()
    backend.dispose()
    answer = 'fail'
    await openClaim(await session('monsoon', '17:05'))
    await waitFor(() => expect(screen.queryByTestId('claim-next-loading')).toBeNull())
    expect(screen.queryByTestId('claim-next-steps')).toBeNull()
    expect(screen.getByTestId('claim-stepper')).toBeTruthy()
  })

  it('is not there while the credit is on its way', async () => {
    stubClaims([areaCreditPending()])
    await openClaim(await session('monsoon', '17:00'))
    expect(screen.getByTestId('claim-step-paid').getAttribute('data-status')).toBe('current')
    expect(screen.queryByTestId('claim-next-steps')).toBeNull()
  })

  it('is not there for a claim that was not paid', async () => {
    stubClaims([areaDeclined()])
    await openClaim(await session('monsoon', '17:05'))
    expect(screen.queryByTestId('claim-next-steps')).toBeNull()
  })

  it('speaks Hindi by default', async () => {
    await openClaim(await session('monsoon', '17:05'), 'CL-000142', '?')
    const card = await screen.findByTestId('claim-next-steps')
    expect(within(card).getByRole('heading').textContent).toBe(hi['claim.next.title'])
    await waitFor(() => expect(text('claim-next-cover')).toContain('22 अगस्त'))
    expect(text('claim-next-wrong')).toContain(hi['claim.next.wrong'])
    expect(text('claim-next-money')).toContain('₹1,380')
  })
})

describe('a claim that is not there, or does not load', () => {
  it('says it could not find an unknown claim and links back to the claims', async () => {
    await openClaim(await session('monsoon', '17:05'), 'CL-999999', '?lang=en', 'error')
    expect(text('app-error')).toContain('We could not find this.')
    const back = within(screen.getByTestId('app-error')).getByRole('link')
    expect(back.getAttribute('href')).toBe('/merchant/S-0142/app?lang=en&screen=claims')
  })

  it('treats a link with no valid claim id as not found without asking for anything', async () => {
    backend = (await session('monsoon', '17:05')).backend
    renderStandalone('/merchant/S-0142/app?lang=en&screen=claim&claim=oops', backend)
    await waitFor(() => expect(screen.getByTestId('screen-claim').getAttribute('data-state')).toBe('error'))
    expect(text('app-error')).toContain('We could not find this.')
  })

  it('shows the error state with Retry when the claims do not load', async () => {
    const real = ApiClient.prototype.list
    vi.spyOn(ApiClient.prototype, 'list').mockImplementation(function (this: ApiClient, path: string, signal?: AbortSignal) {
      if (path.endsWith('/claims')) return Promise.reject(new ApiError('internal_error', 'boom', 500))
      return real.call(this, path, signal)
    })
    await openClaim(await session('monsoon', '17:05'), 'CL-000142', '?lang=en', 'error')
    expect(text('app-error')).toContain('Error code: internal_error')
    expect(screen.getByTestId('app-error-retry')).toBeTruthy()
  })

  it('draws a skeleton with five step rows while loading', async () => {
    const kit = await session('monsoon', '17:05')
    backend = kit.backend
    renderStandalone('/merchant/S-0142/app?lang=en&screen=claim&claim=CL-000142', kit.backend)
    const root = screen.getByTestId('screen-claim')
    expect(root.getAttribute('data-state')).toBe('loading')
    expect(root.getAttribute('aria-busy')).toBe('true')
    expect(within(root).getAllByTestId('claim-skeleton-step')).toHaveLength(5)
    await waitFor(() => expect(root.getAttribute('data-state')).toBe('ready'))
  })
})
