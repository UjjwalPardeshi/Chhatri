/** Cards 6.2 and 6.3 wired into the console: the W key, the key list, and the ops numbers reaching the moment card. */
import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MockBackend } from '../../mock/backend'
import { testBackend } from '../../mock/testkit'
import { momentOps } from '../../pages/Live'
import { clickWhatIf, offlineTiles, renderApp } from '../../test/renderApp'

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  offlineTiles()
  backend = testBackend()
  window.sessionStorage.clear()
  window.localStorage.clear()
})
afterEach(() => {
  backend.dispose()
  vi.unstubAllEnvs()
})

const drawerText = 'Read-only: nothing is saved'
const press = (key: string, target: Element = document.body) => fireEvent.keyDown(target, { key })

describe('the W key', () => {
  beforeEach(() => vi.stubEnv('VITE_FEATURES', 'console_polish,h24_whatif'))

  it('opens and closes the drawer while presenter mode is on, and lists itself before "?"', async () => {
    renderApp('/live', backend)
    fireEvent.click(await screen.findByRole('button', { name: 'Present' }))
    press('W')
    expect(await screen.findByText(drawerText)).toBeTruthy()
    press('w')
    expect(screen.queryByText(drawerText)).toBeNull()
    press('?')
    const keys = within(await screen.findByRole('region', { name: 'Presenter keys' })).getAllByRole('term').map((t) => t.textContent)
    expect(keys).toEqual(['P', 'Space', '1 to 4', 'S', 'W', '?', 'Esc'])
  })

  it('does nothing while presenter mode is off, or while a number is being typed', async () => {
    renderApp('/live', backend)
    await screen.findByRole('button', { name: 'Present' })
    press('W')
    expect(screen.queryByText(drawerText)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Present' }))
    await clickWhatIf()
    const shops = await screen.findByRole('spinbutton')
    press('w', shops)
    expect(screen.getByText(drawerText)).toBeTruthy()
  })

  it('does nothing without the h24_whatif flag', async () => {
    vi.stubEnv('VITE_FEATURES', 'console_polish')
    renderApp('/live', backend)
    fireEvent.click(await screen.findByRole('button', { name: 'Present' }))
    press('W')
    expect(screen.queryByText(drawerText)).toBeNull()
    press('?')
    expect(within(await screen.findByRole('region', { name: 'Presenter keys' })).queryByText('W')).toBeNull()
  })
})

describe('the ops numbers on the moment card', () => {
  it('passes the payouts in flight only when there are some, and the holiday outcomes as they are', () => {
    expect(momentOps(null)).toBeNull()
    const base = { payouts_today: { pending_count: 0 }, holiday_requests_today: null } as never
    expect(momentOps(base)).toEqual({ pendingPayouts: null, holidayRequests: null })
    const flight = { payouts_today: { pending_count: 7 }, holiday_requests_today: { GRANTED: 5, REFUSED: 0, NO_RESPONSE: 0, REQUESTED: 2 } } as never
    expect(momentOps(flight)).toEqual({ pendingPayouts: 7, holidayRequests: { GRANTED: 5, REFUSED: 0, NO_RESPONSE: 0, REQUESTED: 2 } })
  })

  it('words the holiday requests on the card once the ops summary has arrived', async () => {
    vi.stubEnv('VITE_FEATURES', 'console_polish,h8_ops_strip,x4_lender_request')
    const { api } = renderApp('/live', backend)
    await api.seek('17:05')
    const card = await waitFor(() => {
      const found = document.querySelector('.moment')
      expect(found?.textContent).toMatch(/holiday requests?, \d+ granted/)
      return found as HTMLElement
    })
    // With lender answers in, the instalment moment says the holiday line alone (fs-08 13.4).
    expect(card.textContent).not.toContain('paused')
  })
})
