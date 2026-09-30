/** SPEC §13.6 three live tests (EXPLAINED, HUMAN, BLOCKED) and the illness happy path, on the mock. */
import { afterEach, describe, expect, it } from 'vitest'

import type { MockBackend } from './backend'
import { officerDecide } from './cases'
import { inboundPhoto, inboundText, inboundVoiceDemo, inboundVoiceUpload, simulatedLinkUrl } from './conversation'
import { MERCHANTS } from './fixtures'
import { testBackend } from './testkit'

let backend: MockBackend
afterEach(() => backend?.dispose())

const texts = (b: MockBackend, id: string) => b.runtime.messages.filter((m) => m.merchant_id === id).map((m) => m.text_en ?? m.card?.amount_label)

describe('EXPLAINED', () => {
  it('explains ₹4,380 / 63% and opens case C-2291 on a dispute', () => {
    backend = testBackend()
    backend.seek('17:05')
    inboundVoiceDemo(backend.runtime, 'S-0142', 'why')
    const explain = backend.runtime.messages.at(-1)
    expect(explain?.text_hi).toBe('आपका आम मंगलवार: ₹4,380। आज आपके इलाके की बिक्री 63% गिरी। छतरी खोई हुई बिक्री का आधा देती है।')
    expect(explain?.text_en).toBe('Your usual Tuesday: ₹4,380. Your area fell 63%. Chhatri pays half the lost sales.')
    inboundText(backend.runtime, 'S-0142', 'मेरा नुकसान ज़्यादा हुआ।')
    const [ack, chip] = backend.runtime.messages.slice(-2)
    expect(ack.text_hi).toBe('ठीक है, मैं इसे हमारी टीम को भेज रहा हूँ। 24 घंटे में जवाब मिलेगा।')
    expect(chip).toMatchObject({ kind: 'CASE_CHIP', text_en: 'Sent to a claims officer · case C-2291', meta: { case_id: 'C-2291' } })
    expect(backend.runtime.cases[0]).toMatchObject({ id: 'C-2291', kind: 'DISPUTE', status: 'OPEN', due_by: '2025-08-20T17:05:00+05:30' })
    expect(backend.runtime.cases[0].evidence.precedents).toEqual([])
  })

  it('answers FALLBACK_HELP before any payout and for unknown text', () => {
    backend = testBackend()
    inboundVoiceDemo(backend.runtime, 'S-0142', 'why')
    expect(backend.runtime.messages.at(-1)?.text_en).toMatch(/^I'm Chhatri/)
    inboundText(backend.runtime, 'S-0142', 'hello there')
    expect(backend.runtime.messages.at(-1)?.text_en).toMatch(/^I'm Chhatri/)
  })

  it('officer upholds a dispute without new money', () => {
    backend = testBackend()
    backend.seek('17:05')
    inboundText(backend.runtime, 'S-0142', 'My loss was bigger')
    const before = backend.runtime.payouts.length
    const resolved = officerDecide(backend.runtime, MERCHANTS['S-0142'], 'C-2291', true, '')
    expect(resolved.case).toMatchObject({ status: 'CLOSED', resolution: 'Payout confirmed by a claims officer', resolved_by: 'officer:officer' })
    expect(resolved.decision?.outcome).toBe('APPROVED')
    expect(backend.runtime.payouts.length).toBe(before)
    expect(() => officerDecide(backend.runtime, MERCHANTS['S-0142'], 'C-2291', true, '')).toThrow(/already CLOSED/)
    expect(() => officerDecide(backend.runtime, MERCHANTS['S-0142'], 'C-9999', true, '')).toThrow(/not found/)
  })
})

function illness(name: 'illness' | 'illness_mismatch', slip: string) {
  backend = testBackend()
  backend.load(name)
  backend.seek('11:20')
  inboundVoiceDemo(backend.runtime, 'S-0142', 'ill')
  inboundPhoto(backend.runtime, 'S-0142', `/slips/${slip}`, slip)
  return backend
}

describe('illness happy path', () => {
  it('checks in at 11:20, asks for the slip and pays ₹1,500 four minutes later', () => {
    const b = illness('illness', 'anil_admission_slip.png')
    const all = texts(b, 'S-0142')
    expect(all[0]).toBe('Your shop has been closed since yesterday. Is everything okay?')
    expect(all).toContain('Get well soon. Please send one photo of the hospital slip.')
    expect(b.runtime.decisions[0]).toMatchObject({ outcome: 'APPROVED', amount_label: '₹1,500' })
    expect(b.runtime.decisions[0].explanation?.formula_en).toBe('½ × ₹4,380 = ₹2,190 a day, capped at ₹1,500 × 1 day = ₹1,500')
    b.step(5)
    expect(b.runtime.payouts[0]).toMatchObject({ status: 'CREDITED', credited_at: '2025-08-21T11:24:00+05:30' })
    expect(texts(b, 'S-0142')).toContain("Anil ji, your claim is approved. ₹1,500 credited with today's settlement.")
    expect(b.runtime.pauses).toHaveLength(1)
  })

  it('treats an unknown upload as unreadable and refers it', () => {
    backend = testBackend()
    backend.load('illness')
    backend.seek('11:21')
    inboundVoiceUpload(backend.runtime, 'S-0142', 'blob:voice')
    inboundPhoto(backend.runtime, 'S-0142', 'blob:photo', null)
    expect(backend.runtime.decisions[0].outcome).toBe('REFERRED')
    expect(backend.runtime.messages.at(-2)?.text_en).toMatch(/couldn't read the slip/)
  })
})

describe('HUMAN', () => {
  it('refers a slip for "Sunil Pawar" and pays only after the officer approves', () => {
    const b = illness('illness_mismatch', 'mismatch_admission_slip.png')
    const decision = b.runtime.decisions[0]
    expect(decision.outcome).toBe('REFERRED')
    expect(decision.checks.find((c) => c.code === 'NAME_MATCHES_KYC')?.status).toBe('FAIL')
    expect(b.runtime.cases[0]).toMatchObject({ id: 'C-2291', kind: 'PERSONAL_CLAIM_REVIEW' })
    expect(b.runtime.cases[0].evidence).toMatchObject({ kyc_name: 'ANIL RAMESH JADHAV', name_score: 41, silent_days: ['2025-08-20'] })
    expect(texts(b, 'S-0142')).toContain("Thank you. The name on the slip doesn't match your KYC, so our team will check it. You'll hear back within 24 hours.")
    b.step(30)
    expect(b.runtime.payouts).toEqual([])
    officerDecide(b.runtime, MERCHANTS['S-0142'], 'C-2291', true, 'Called the hospital')
    const approved = b.runtime.decisions.at(-1)
    expect(approved).toMatchObject({ outcome: 'APPROVED', decided_by: 'officer:officer', supersedes: decision.id, amount_label: '₹1,500' })
    expect(approved?.checks.filter((c) => c.severity === 'SOFT').every((c) => c.status === 'WAIVED_BY_OFFICER')).toBe(true)
    b.step(4)
    expect(b.runtime.payouts[0]).toMatchObject({ status: 'CREDITED', amount_label: '₹1,500' })
    expect(texts(b, 'S-0142')).toContain('Anil ji, our team approved your claim. ₹1,500 credited.')
  })

  it('declines with a reason message', () => {
    const b = illness('illness_mismatch', 'mismatch_admission_slip.png')
    const declined = officerDecide(b.runtime, MERCHANTS['S-0142'], 'C-2291', false, '')
    expect(declined.case).toMatchObject({ status: 'DECLINED', resolution: 'Declined by officer:officer' })
    expect(b.runtime.decisions.at(-1)).toMatchObject({ outcome: 'DECLINED', amount_label: '₹0' })
    expect(b.runtime.messages.at(-1)?.text_en).toMatch(/^Anil ji, our team reviewed your claim\./)
  })

  it('ignores a slip before the check-in', () => {
    backend = testBackend()
    backend.load('illness')
    inboundPhoto(backend.runtime, 'S-0142', '/slips/anil_admission_slip.png', 'anil_admission_slip.png')
    expect(backend.runtime.decisions).toEqual([])
  })
})

describe('BLOCKED', () => {
  it('blocks cover bought after the alert and still offers the Paytm link', () => {
    backend = testBackend()
    backend.load('buy_cover')
    backend.seek('18:10')
    inboundText(backend.runtime, 'S-0907', 'Red alert tomorrow. Cover me today.')
    const [inbound, blocked, link] = backend.runtime.messages.filter((m) => m.merchant_id === 'S-0907')
    expect(inbound).toMatchObject({ direction: 'INBOUND', text_hi: null, text_en: 'Red alert tomorrow. Cover me today.' })
    expect(blocked.text_hi).toBe('नया कवर वेटिंग पीरियड के बाद शुरू होता है — 25 अगस्त से। कल के अलर्ट पर यह लागू नहीं होगा।')
    expect(blocked.text_en).toBe("New cover starts after the waiting period — from 25 August. It won't apply to tomorrow's alert.")
    expect(link.text_en).toMatch(/^To buy cover for later, pay ₹90 \(₹3\/day\) here: https:\/\/paytm\.me\/sim-[0-9A-F]{6}$/)
    expect(link.text_en).toContain(simulatedLinkUrl('S-0907', 9_000, 'PR-000001'))
  })

  it('does not sell a covered merchant a second cover', () => {
    backend = testBackend()
    inboundText(backend.runtime, 'S-0142', 'cover me')
    expect(backend.runtime.messages.at(-1)?.text_en).toMatch(/^I'm Chhatri/)
  })
})
