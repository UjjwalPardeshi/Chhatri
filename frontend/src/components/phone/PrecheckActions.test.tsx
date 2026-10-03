/**
 * The pre-check and the doctor question on the console phone (design 2.6, findings 1, 2 and 4): the buttons follow the
 * card's `actions[].enabled`, the six fields and the checklist show on every pre-check card, an answer leaves a neutral
 * thank-you line, and a 409 reads as a friendly bilingual line, never the server's message.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import type { Message } from '../../api/types'
import { READY_PRECHECK, RETAKE_PRECHECK } from '../../miniapp/api/precheckFixtures'
import { ConsentActions } from './ConsentActions'
import { consentCardOf, precheckCardOf } from './precheckCard'
import { openPrecheck, PrecheckActions } from './PrecheckActions'
import { PrecheckFields } from './PrecheckFields'

type Confirm = (id: string, pc: string, action: string) => Promise<unknown>
/** A fresh fake confirm route per test (a module-level mock reset between tests reports its caught rejections). */
const live = vi.hoisted(() => ({ confirm: null as unknown as ReturnType<typeof vi.fn<Confirm>> }))
vi.mock('../../state/live', () => ({ useLive: () => ({ api: { confirmSlipPrecheck: (...args: Parameters<Confirm>) => live.confirm(...args) } }) }))

const ACTION_LABELS = {
  CONFIRM_FIELDS: { label_hi: 'हाँ, सही है', label_en: 'Yes, this is right' },
  RETAKE_PHOTO: { label_hi: 'दूसरी फ़ोटो भेजें', label_en: 'Send another photo' },
  SEND_TO_TEAM: { label_hi: 'हमारी टीम को भेजें', label_en: 'Send to our team' },
} as const
const CHECKLIST_TEXT = { text_hi: 'फ़ोटो पढ़ी जा सकी', text_en: 'The photo could be read' }

/** The chat card of design 2.6: the pre-check view, the checklist with its sentences and the three actions. */
function card(base: typeof READY_PRECHECK, enabled: { CONFIRM_FIELDS: boolean; RETAKE_PHOTO: boolean; SEND_TO_TEAM: boolean }) {
  return {
    ...base,
    checklist: base.checklist.map((line) => ({ ...line, ...CHECKLIST_TEXT })),
    actions: (Object.keys(ACTION_LABELS) as (keyof typeof ACTION_LABELS)[]).map((kind) => ({ kind, ...ACTION_LABELS[kind], enabled: enabled[kind] })),
  }
}

const READY_CARD = card(READY_PRECHECK, { CONFIRM_FIELDS: true, RETAKE_PHOTO: true, SEND_TO_TEAM: false })
const RETAKE_CARD = card(RETAKE_PRECHECK, { CONFIRM_FIELDS: false, RETAKE_PHOTO: true, SEND_TO_TEAM: true })
const NEEDS_TEAM_CARD = { ...card(RETAKE_PRECHECK, { CONFIRM_FIELDS: false, RETAKE_PHOTO: false, SEND_TO_TEAM: true }), status: 'NEEDS_TEAM' }
const MISMATCH_CARD = { ...READY_CARD, slots: READY_CARD.slots.map((slot) => (slot.key === 'patient_name' ? { ...slot, value: 'Sunil Pawar' } : slot)) }
const CONSENT_CARD = {
  consent_for: 'PC-000001',
  purpose: 'doctor_verification',
  doctor_name: 'Dr S. Rao',
  hospital_name: 'KEM Hospital, Parel',
  actions: [
    { kind: 'CONSENT_YES', label_hi: 'हाँ, पूछ लीजिए', label_en: 'Yes, ask them' },
    { kind: 'CONSENT_NO', label_hi: 'नहीं', label_en: 'No' },
  ],
}

function message(cardValue: unknown, extra: Partial<Message> = {}): Message {
  return { id: 'M-1', merchant_id: 'S-0142', direction: 'OUTBOUND', channel: 'SIMULATOR', kind: 'TEXT', text_hi: null, text_en: 'Is this right?', audio_url: null, media_url: null, card: cardValue, created_at: '2025-08-21T11:25:00+05:30', meta: {}, ...extra } as unknown as Message
}

function actionsFor(cardValue: unknown) {
  const m = message(cardValue)
  const found = precheckCardOf(m)
  if (!found) throw new Error('no pre-check card')
  return render(<PrecheckActions message={m} card={found} />)
}

beforeEach(() => {
  live.confirm = vi.fn<Confirm>()
})

describe('openPrecheck and the card readers', () => {
  it('finds a READY, RETAKE or NEEDS_TEAM pre-check card', () => {
    expect(openPrecheck(message(READY_CARD))?.precheck_id).toBe('PC-000001')
    expect(openPrecheck(message(RETAKE_CARD))?.status).toBe('RETAKE')
    expect(openPrecheck(message(NEEDS_TEAM_CARD))?.status).toBe('NEEDS_TEAM')
  })

  it.each([null, {}, { ...READY_CARD, status: 'CONFIRMED' }, { ...READY_CARD, precheck_id: 7 }, 'text', CONSENT_CARD])('ignores %j', (value) => {
    expect(openPrecheck(message(value))).toBeNull()
  })

  it('reads the consent card, and nothing else as one', () => {
    expect(consentCardOf(message(CONSENT_CARD))?.consent_for).toBe('PC-000001')
    expect(consentCardOf(message(READY_CARD))).toBeNull()
    expect(consentCardOf(message({ ...CONSENT_CARD, consent_for: 'X' }))).toBeNull()
  })
})

describe('PrecheckActions', () => {
  it('READY offers only "Yes, this is right", which confirms', async () => {
    live.confirm.mockResolvedValue({})
    actionsFor(READY_CARD)
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual(['हाँ, सही है · Yes, this is right'])
    fireEvent.click(screen.getByRole('button', { name: /Yes, this is right/ }))
    await waitFor(() => expect(live.confirm).toHaveBeenCalledWith('S-0142', 'PC-000001', 'CONFIRM'))
  })

  it.each([
    ['RETAKE', RETAKE_CARD],
    ['NEEDS_TEAM', NEEDS_TEAM_CARD],
  ])('%s offers only "Send to our team", which sends it to the team', async (_status, value) => {
    live.confirm.mockResolvedValue({})
    actionsFor(value)
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual(['हमारी टीम को भेजें · Send to our team'])
    fireEvent.click(screen.getByRole('button', { name: /Send to our team/ }))
    await waitFor(() => expect(live.confirm).toHaveBeenCalledWith('S-0142', 'PC-000001', 'SEND_TO_TEAM'))
  })

  it('after an answer the buttons go and a neutral thank-you line stays', async () => {
    live.confirm.mockResolvedValue({})
    actionsFor(READY_CARD)
    fireEvent.click(screen.getByRole('button', { name: /Yes, this is right/ }))
    expect(await screen.findByText('धन्यवाद, आपका जवाब मिल गया।')).toBeTruthy()
    expect(screen.getByText('Thank you, we have your answer.')).toBeTruthy()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it.each([
    ['already_confirmed', 'यह जवाब पहले ही दर्ज है।', 'This answer is already recorded.'],
    ['superseded', 'नई फ़ोटो ने इसकी जगह ले ली है।', 'A newer photo replaced this one.'],
    ['consent_pending', 'पहले डॉक्टर वाले सवाल का जवाब दीजिए।', 'Please answer the question about the doctor first.'],
  ])('a 409 %s reads as a friendly line, never the server message', async (code, hi, en) => {
    live.confirm.mockImplementation(async () => {
      throw new ApiError(code, `pre-check PC-000001 says ${code}`, 409)
    })
    actionsFor(READY_CARD)
    fireEvent.click(screen.getByRole('button', { name: /Yes, this is right/ }))
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain(hi)
    expect(alert.textContent).toContain(en)
    expect(alert.textContent).not.toContain('PC-000001 says')
  })

  it('an answer that is already recorded retires the buttons too', async () => {
    live.confirm.mockImplementation(async () => {
      throw new ApiError('already_confirmed', 'x', 409)
    })
    actionsFor(READY_CARD)
    fireEvent.click(screen.getByRole('button', { name: /Yes, this is right/ }))
    await screen.findByRole('alert')
    expect(screen.queryByRole('button')).toBeNull()
  })
})

describe('PrecheckFields', () => {
  it('shows the six fields with the doctor and the registration number, and the checklist, never a confidence', () => {
    const found = precheckCardOf(message(READY_CARD))
    if (!found) throw new Error('no card')
    const { container } = render(<PrecheckFields card={found} />)
    const text = container.textContent ?? ''
    expect(text).toContain('Anil R. Jadhav')
    expect(text).toContain('Dr S. Rao')
    expect(text).toContain('MMC-2011-45817')
    expect(text).toContain('Registration no.')
    expect(text).toContain('not on the slip')
    expect(text).toContain('The photo could be read')
    expect(text).not.toContain('0.94')
    expect(text).not.toMatch(/%|confidence/i)
  })

  it('shows the name as read on a mismatching slip', () => {
    const found = precheckCardOf(message(MISMATCH_CARD))
    if (!found) throw new Error('no card')
    render(<PrecheckFields card={found} />)
    expect(screen.getByText('Sunil Pawar')).toBeTruthy()
  })
})

describe('ConsentActions', () => {
  it('Yes answers CONSENT_YES and No answers CONSENT_NO, then thanks the merchant', async () => {
    live.confirm.mockResolvedValue({})
    const m = message(CONSENT_CARD)
    const found = consentCardOf(m)
    if (!found) throw new Error('no card')
    const { unmount } = render(<ConsentActions message={m} card={found} />)
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual(['हाँ, पूछ लीजिए · Yes, ask them', 'नहीं · No'])
    fireEvent.click(screen.getByRole('button', { name: /Yes, ask them/ }))
    await waitFor(() => expect(live.confirm).toHaveBeenCalledWith('S-0142', 'PC-000001', 'CONSENT_YES'))
    expect(await screen.findByText('Thank you, we have your answer.')).toBeTruthy()
    unmount()
    render(<ConsentActions message={m} card={found} />)
    fireEvent.click(screen.getByRole('button', { name: /No/ }))
    await waitFor(() => expect(live.confirm).toHaveBeenLastCalledWith('S-0142', 'PC-000001', 'CONSENT_NO'))
  })
})
