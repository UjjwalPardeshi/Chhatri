/** N3 slip pre-check (fs-02 7.3, screens-and-flows 6): read, show what was read, confirm / retake / send to the team. */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ScenarioName } from '../../api/types'
import type { MockBackend } from '../../mock/backend'
import { MOCK_OFFICER_TOKEN } from '../../mock/fixtures'
import { testApi } from '../../mock/testkit'
import { renderStandalone } from '../shell/shellKit'

let backend: MockBackend
beforeEach(() => {
  vi.stubEnv('VITE_FEATURES', 'n1_miniapp,n3_slip_precheck')
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  window.localStorage.clear()
})
afterEach(() => {
  backend?.dispose()
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
})

type Options = { search?: string; scenario?: ScenarioName; at?: string }

async function openSlip({ search = '?lang=en&screen=slip', scenario = 'illness', at = '11:30' }: Options = {}) {
  const kit = testApi()
  backend = kit.backend
  await kit.api.load(scenario)
  await kit.api.seek(at)
  renderStandalone(`/merchant/S-0142/app${search}`, kit.backend, kit.api)
  await screen.findByTestId('screen-slip')
  return kit
}

function deferred() {
  const hold: { resolve: (value: unknown) => void } = { resolve: () => undefined }
  const promise = new Promise<unknown>((resolve) => { hold.resolve = resolve })
  return { promise, resolve: (value: unknown) => hold.resolve(value) }
}

const text = (id: string) => screen.getByTestId(id).textContent ?? ''
const png = (name = 'mine.png', size = 8) => new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47, ...Array.from({ length: size - 4 }, () => 1)])], name, { type: 'image/png' })
const pick = (testId: string, file: File) => fireEvent.change(screen.getByTestId(testId), { target: { files: [file] } })
const demo = async (id: 'slip-demo-good' | 'slip-demo-blurry') => {
  fireEvent.click(screen.getByTestId(id))
  return screen.findByTestId('slip-result')
}

describe('the flag', () => {
  it('shows Home when the flag is off, so the sheet does not exist', async () => {
    vi.stubEnv('VITE_FEATURES', 'n1_miniapp')
    const kit = testApi()
    backend = kit.backend
    await kit.api.load('illness')
    renderStandalone('/merchant/S-0142/app?lang=en&screen=slip', kit.backend, kit.api)
    await screen.findByTestId('screen-home')
    expect(screen.queryByTestId('screen-slip')).toBeNull()
  })
})

describe('idle', () => {
  it('shows the title, the help line, two photo buttons, the notice and the SIMULATED line, and reads nothing yet', async () => {
    const { backend: b } = await openSlip()
    expect(screen.getByTestId('screen-slip').getAttribute('data-state')).toBe('ready')
    expect(text('screen-slip')).toContain('Take one photo of the admission slip')
    expect(text('slip-notice')).toContain('Please send a sample slip, not a real one.')
    expect(text('slip-sim')).toContain('SIMULATED slip reading.')
    expect(screen.getByTestId('slip-take').textContent).toBe('Take a photo')
    expect(screen.getByTestId('slip-gallery').textContent).toBe('Choose from the gallery')
    expect(screen.getByTestId('slip-camera-input').getAttribute('capture')).toBe('environment')
    expect(b.runtime.audit.some((e) => e.action === 'precheck.shown')).toBe(false)
  })

  it('is Hindi first', async () => {
    await openSlip({ search: '?screen=slip' })
    expect(text('screen-slip')).toContain('भर्ती की पर्ची, छुट्टी का काग़ज़ या बिल की एक फ़ोटो लीजिए')
    expect(screen.getByTestId('slip-take').textContent).toBe('फ़ोटो लें')
  })
})

describe('READY', () => {
  it('shows what was read as plain text, three checklist lines, the discharge note and the two buttons', async () => {
    await openSlip()
    const result = await demo('slip-demo-good')
    expect(result.getAttribute('data-status')).toBe('READY')
    expect(text('slip-result')).toContain('We have read your slip. Please check it. Is this right?')
    expect(text('slip-field-patient_name')).toContain('Anil R. Jadhav')
    expect(text('slip-field-admission_date')).toContain('20 August')
    expect(text('slip-field-discharge_date')).toContain('Not on the slip')
    expect(text('slip-field-hospital_name')).toContain('KEM Hospital, Parel')
    expect(screen.getAllByTestId(/^slip-check-/)).toHaveLength(3)
    expect(text('slip-check-photo_readable')).toBe('The photo could be read')
    expect(text('slip-notes')).toContain('There is no discharge date on the slip.')
    expect(screen.getByTestId('slip-confirm').textContent).toBe('Yes, this is right')
    expect(screen.getByTestId('slip-retake').textContent).toBe('Send another photo')
    expect(screen.queryByTestId('slip-team')).toBeNull()
  })

  it('shows no confidence, no percentage and no number except the date (H5)', async () => {
    await openSlip()
    await demo('slip-demo-good')
    const withoutDate = text('screen-slip').replace(/20 August(?: 2025)?/g, '')
    expect(withoutDate).not.toMatch(/\d/)
    expect(withoutDate).not.toMatch(/confidence|%/i)
  })

  it('labels the mode and opens the details with the provider and the reason', async () => {
    await openSlip()
    await demo('slip-demo-good')
    expect(screen.getByTestId('slip-mode').getAttribute('data-mode')).toBe('SIMULATED')
    expect(text('slip-details')).toContain('Read by: mock')
    expect(text('slip-details')).toContain('Reason: MOCK_BACKEND')
  })

  it('confirming decides the claim and opens its detail', async () => {
    const { backend: b } = await openSlip()
    await demo('slip-demo-good')
    expect(b.runtime.decisions.filter((d) => d.merchant_id === 'S-0142')).toHaveLength(0)
    fireEvent.click(screen.getByTestId('slip-confirm'))
    await screen.findByTestId('screen-claim')
    expect(b.runtime.decisions.some((d) => d.merchant_id === 'S-0142' && d.outcome === 'APPROVED')).toBe(true)
  })
})

describe('retake', () => {
  it('a blurry photo says why in one plain sentence and offers another photo or the team, never "failed"', async () => {
    await openSlip()
    const result = await demo('slip-demo-blurry')
    expect(result.getAttribute('data-status')).toBe('RETAKE')
    expect(text('slip-guidance')).toBe('The photo is not clear. Please take it in good light, with the slip flat and fully in view.')
    expect(text('slip-field-patient_name')).toContain('not clear')
    expect(text('slip-check-photo_readable')).toBe('The photo is not clear')
    expect(screen.getByTestId('slip-retake').textContent).toBe('Send another photo')
    expect(screen.getByTestId('slip-team').textContent).toBe('Send to our team')
    expect(screen.queryByTestId('slip-confirm')).toBeNull()
    expect(text('screen-slip')).not.toMatch(/failed/i)
  })

  it('another photo replaces the check; the third that is not ready leaves only the team button', async () => {
    await openSlip()
    await demo('slip-demo-blurry')
    pick('slip-camera-input', png())
    await waitFor(() => expect(screen.getByTestId('slip-result').getAttribute('data-attempt')).toBe('2'))
    expect(screen.getByTestId('slip-retake')).toBeTruthy()
    pick('slip-gallery-input', png('again.png'))
    await waitFor(() => expect(screen.getByTestId('slip-result').getAttribute('data-attempt')).toBe('3'))
    expect(screen.getByTestId('slip-result').getAttribute('data-status')).toBe('NEEDS_TEAM')
    expect(text('slip-guidance')).toContain('You have already sent several photos.')
    expect(screen.queryByTestId('slip-retake')).toBeNull()
    expect(screen.getByTestId('slip-team')).toBeTruthy()
  })

  it('sending to the team files the claim as referred and opens it', async () => {
    const { backend: b } = await openSlip()
    await demo('slip-demo-blurry')
    fireEvent.click(screen.getByTestId('slip-team'))
    await screen.findByTestId('screen-claim')
    expect(b.runtime.decisions.some((d) => d.merchant_id === 'S-0142' && d.outcome === 'REFERRED')).toBe(true)
    expect(b.runtime.cases.length).toBeGreaterThan(0)
  })
})

describe('reading, errors and offline', () => {
  it('shows the reading state with Cancel, and Cancel drops the answer', async () => {
    const kit = await openSlip()
    const gate = deferred()
    vi.spyOn(kit.api, 'slipPrecheck').mockReturnValue(gate.promise as never)
    fireEvent.click(screen.getByTestId('slip-demo-good'))
    await screen.findByTestId('slip-reading')
    expect(text('slip-reading')).toContain('Reading your slip…')
    fireEvent.click(screen.getByTestId('slip-cancel'))
    expect(screen.queryByTestId('slip-reading')).toBeNull()
    gate.resolve({})
    await waitFor(() => expect(screen.getByTestId('slip-take')).toBeTruthy())
  })

  it('checks the size and the type before any upload', async () => {
    const kit = await openSlip()
    const spy = vi.spyOn(kit.api, 'slipPrecheck')
    pick('slip-gallery-input', new File(['x'], 'doc.pdf', { type: 'application/pdf' }))
    expect(text('slip-error')).toBe('Please send a JPG, PNG or WebP photo.')
    const big = png('big.png')
    Object.defineProperty(big, 'size', { value: 6 * 1024 * 1024 })
    pick('slip-gallery-input', big)
    expect(text('slip-error')).toBe('The photo is too big. The limit is 5 MB.')
    expect(spy).not.toHaveBeenCalled()
  })

  it('says so when no check-in is open (409) and offers the photo buttons again', async () => {
    await openSlip({ at: '10:45' })
    fireEvent.click(screen.getByTestId('slip-demo-good'))
    await waitFor(() => expect(text('slip-error')).toContain('no open check-in'))
    expect(screen.getByTestId('slip-take')).toBeTruthy()
  })

  it('shows the generic error for a body that breaks the contract', async () => {
    const kit = await openSlip()
    vi.spyOn(kit.api, 'slipPrecheck').mockResolvedValue({ status: 'READY' } as never)
    fireEvent.click(screen.getByTestId('slip-demo-good'))
    await waitFor(() => expect(text('slip-error')).toBe('Something went wrong. Try again.'))
  })

  it('disables the photo buttons offline and says why', async () => {
    await openSlip()
    vi.spyOn(window.navigator, 'onLine', 'get').mockReturnValue(false)
    window.dispatchEvent(new Event('offline'))
    await waitFor(() => expect((screen.getByTestId('slip-take') as HTMLButtonElement).disabled).toBe(true))
    expect((screen.getByTestId('slip-gallery') as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByTestId('screen-slip').textContent).toContain('This needs the internet.')
  })
})

describe('the OK to read the slip (n6_consents, fs-07 9.3)', () => {
  beforeEach(() => vi.stubEnv('VITE_FEATURES', 'n1_miniapp,n3_slip_precheck,n6_consents'))

  it('asks nothing while the seeded slip consent is ACTIVE', async () => {
    await openSlip()
    expect(screen.queryByTestId('slip-consent')).toBeNull()
    expect((screen.getByTestId('slip-take') as HTMLButtonElement).disabled).toBe(false)
  })

  it('asks for the OK once the slip consent is off, and sends it with the photo, which the server records', async () => {
    const kit = testApi()
    backend = kit.backend
    await kit.api.load('illness')
    await kit.api.seek('11:30')
    kit.client.setOfficerToken(MOCK_OFFICER_TOKEN)
    const slip = (await kit.api.consents('S-0142'))[1]
    await kit.api.withdrawConsent('S-0142', slip.consent_id ?? '')
    renderStandalone('/merchant/S-0142/app?lang=en&screen=slip', kit.backend, kit.api)
    const box = (await screen.findByTestId('slip-consent')) as HTMLInputElement
    expect(box.checked).toBe(false)
    expect(screen.getByText('I agree: Chhatri may read a hospital slip when I send one.')).toBeTruthy()
    expect((screen.getByTestId('slip-demo-good') as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByTestId('slip-take') as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(box)
    expect((await demo('slip-demo-good')).getAttribute('data-status')).toBe('READY')
    expect((await kit.api.consents('S-0142'))[1]).toMatchObject({ status: 'ACTIVE', source: 'SLIP_UPLOAD' })
  })
})
