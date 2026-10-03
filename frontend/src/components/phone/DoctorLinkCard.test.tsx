/**
 * The officer's doctor enrolment card on /merchant/:id (design 2.9, D8): per directory doctor the name, the hospital,
 * whether a Telegram chat answers, and Copy link / Open in Telegram / New link. The link is a secret: it is never logged.
 */
import { act, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { DoctorEnrolment } from '../../api/types'
import type { MockBackend } from '../../mock/backend'
import { testApi } from '../../mock/testkit'
import { LiveProvider } from '../../state/live'
import { useDoctorLinks, type DoctorLinksState } from '../../state/useDoctorLinks'
import { DoctorLinkCard, doctorStatus } from './DoctorLinkCard'

const LINK = 'https://t.me/chaatri_paytm_bot?start=DOC-0123456789ABCDEF'
const RAO: DoctorEnrolment = {
  registration_no: 'MMC-2011-45817',
  doctor_name: 'Dr S. Rao',
  hospital_id: 'H-KEM',
  hospital_name: 'KEM Hospital, Parel',
  enrolled: false,
  deep_link: LINK,
  answers: 'SIMULATED',
}

function state(over: Partial<DoctorLinksState> = {}): DoctorLinksState {
  return { on: true, items: [RAO], error: null, busy: null, reset: vi.fn<DoctorLinksState['reset']>(async () => undefined), ...over }
}

afterEach(() => {
  vi.unstubAllEnvs()
})

describe('doctorStatus', () => {
  it('says who answers the doctor question', () => {
    expect(doctorStatus(RAO)).toBe('Not enrolled · the simulated doctor answers')
    expect(doctorStatus({ ...RAO, enrolled: true, answers: 'TELEGRAM' })).toBe('Enrolled · questions go to this Telegram chat')
    expect(doctorStatus({ ...RAO, enrolled: true, answers: 'SIMULATED' })).toBe('Telegram not live · the simulated doctor answers')
    expect(doctorStatus({ ...RAO, answers: 'FORCED' })).toBe('Forced for the demo · no doctor answers, the claim goes to a person')
  })
})

describe('DoctorLinkCard', () => {
  it('renders nothing while the flag is off', () => {
    const { container } = render(<DoctorLinkCard state={state({ on: false })} />)
    expect(container.innerHTML).toBe('')
  })

  it('names the doctor and the hospital, the status, and opens the link in Telegram in a new tab', () => {
    render(<DoctorLinkCard state={state()} />)
    expect(screen.getByText('Dr S. Rao')).toBeTruthy()
    expect(screen.getByText(/KEM Hospital, Parel · MMC-2011-45817/)).toBeTruthy()
    expect(screen.getByTestId('doctor-status-MMC-2011-45817').textContent).toBe('Not enrolled · the simulated doctor answers')
    const open = screen.getByRole('link', { name: 'Open in Telegram' })
    expect([open.getAttribute('href'), open.getAttribute('target'), open.getAttribute('rel')]).toEqual([LINK, '_blank', 'noreferrer'])
  })

  it('copies the link to the clipboard, and never logs it', async () => {
    const writeText = vi.fn<(text: string) => Promise<void>>(async () => undefined)
    vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText } })
    const logs = [vi.spyOn(console, 'log'), vi.spyOn(console, 'warn'), vi.spyOn(console, 'info')]
    render(<DoctorLinkCard state={state()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Copy link' }))
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(LINK))
    expect(await screen.findByText('Link copied')).toBeTruthy()
    for (const spy of logs) expect(JSON.stringify(spy.mock.calls)).not.toContain('DOC-0123456789ABCDEF')
  })

  it('shows the link selected to copy by hand when the clipboard refuses', async () => {
    vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText: vi.fn<(text: string) => Promise<void>>(async () => Promise.reject(new Error('denied'))) } })
    render(<DoctorLinkCard state={state()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Copy link' }))
    const field = (await screen.findByLabelText('Enrolment link for Dr S. Rao')) as HTMLInputElement
    expect(field.value).toBe(LINK)
    expect(field.readOnly).toBe(true)
  })

  it('makes a new link on request', () => {
    const reset = vi.fn<DoctorLinksState['reset']>(async () => undefined)
    render(<DoctorLinkCard state={state({ reset })} />)
    fireEvent.click(screen.getByRole('button', { name: 'New link' }))
    expect(reset).toHaveBeenCalledWith('MMC-2011-45817')
  })

  it('says when the bot is not known yet, with no link buttons', () => {
    render(<DoctorLinkCard state={state({ items: [{ ...RAO, deep_link: null }] })} />)
    expect(screen.queryByRole('link', { name: 'Open in Telegram' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Copy link' })).toBeNull()
    expect(screen.getByText(/No link yet/)).toBeTruthy()
  })
})

function wrapperFor(kit: ReturnType<typeof testApi>) {
  return ({ children }: { children: ReactNode }) => (
    <LiveProvider api={kit.api} mock>
      {children}
    </LiveProvider>
  )
}

describe('useDoctorLinks', () => {
  let backend: MockBackend
  beforeEach(() => vi.stubEnv('VITE_FEATURES', 'telegram_channel'))
  afterEach(() => backend?.dispose())

  it('loads the links with the officer token, and reads them again when a doctor.* audit event arrives', async () => {
    const kit = testApi()
    backend = kit.backend
    const spy = vi.spyOn(kit.api, 'doctorEnrolmentLinks')
    const { result } = renderHook(() => useDoctorLinks(), { wrapper: wrapperFor(kit) })
    await waitFor(() => expect(result.current.items?.[0]?.doctor_name).toBe('Dr S. Rao'))
    const calls = spy.mock.calls.length
    act(() => {
      kit.backend.runtime.record('doctor:MMC-2011-45817', 'doctor.enrolled', 'doctor', 'MMC-2011-45817', { registration_no: 'MMC-2011-45817', hospital_id: 'H-KEM' })
    })
    await waitFor(() => expect(spy.mock.calls.length).toBeGreaterThan(calls))
  })

  it('resets a link and keeps the new item', async () => {
    const kit = testApi()
    backend = kit.backend
    const { result } = renderHook(() => useDoctorLinks(), { wrapper: wrapperFor(kit) })
    await waitFor(() => expect(result.current.items).not.toBeNull())
    await act(() => result.current.reset('MMC-2011-45817'))
    expect(kit.backend.runtime.audit.some((e) => e.action === 'doctor.enrolment_reset')).toBe(true)
    expect(result.current.items?.[0]?.registration_no).toBe('MMC-2011-45817')
  })
})
