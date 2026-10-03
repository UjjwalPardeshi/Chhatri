/** The shell of fs-04 sections 4 and 6: app bar, tab bar, URL state, the replay clock and the scenario reset. */
import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MockBackend } from '../../mock/backend'
import { testBackend } from '../../mock/testkit'
import { renderStandalone } from './shellKit'

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  window.localStorage.clear()
  backend = testBackend()
})
afterEach(() => {
  backend.dispose()
  vi.useRealTimers()
  vi.restoreAllMocks()
})

const where = () => screen.getByTestId('probe-location').textContent
const historyBack = () => fireEvent.click(screen.getByTestId('probe-history-back'))
const current = (tab: string) => screen.getByTestId(`app-tab-${tab}`).getAttribute('aria-current')

describe('the shell', () => {
  it('draws the app bar, Home and three tabs, with Home current and one SIMULATED badge', async () => {
    renderStandalone('/merchant/S-0142/app?lang=en', backend)
    expect((await screen.findByTestId('screen-home')).getAttribute('data-state')).toBe('ready')
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Chhatri')
    expect(screen.getByRole('main').contains(screen.getByTestId('screen-home'))).toBe(true)
    const tabs = screen.getByTestId('app-tabbar')
    expect(tabs.tagName).toBe('NAV')
    expect(tabs.getAttribute('aria-label')).toBe('Main tabs')
    expect(Array.from(tabs.querySelectorAll('a')).map((a) => a.textContent)).toEqual(['Home', 'Claims', 'Help'])
    expect([current('home'), current('claims'), current('help')]).toEqual(['page', null, null])
    expect(screen.getByTestId('app-mode-badge').textContent).toBe('SIMULATED')
    const root = screen.getByTestId('app-root')
    expect(root.classList.contains('miniapp')).toBe(true)
    expect(root.getAttribute('lang')).toBe('en')
  })

  it('shows the replay clock, never the device clock', async () => {
    backend.seek('17:05')
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2031-01-01T03:00:00Z'))
    renderStandalone('/merchant/S-0142/app?lang=en', backend)
    await waitFor(() => expect(screen.getByTestId('app-clock').getAttribute('datetime')).toMatch(/T17:05/))
    const clock = screen.getByTestId('app-clock')
    expect(clock.textContent).toMatch(/^Demo date and time: /)
    expect(clock.textContent).not.toContain('2031')
  })

  it('writes a tab tap to the URL, and the browser Back button returns to the last screen', async () => {
    renderStandalone('/merchant/S-0142/app?lang=en', backend)
    await screen.findByTestId('screen-home')
    fireEvent.click(screen.getByTestId('app-tab-claims'))
    await screen.findByTestId('screen-claims')
    await waitFor(() => expect(screen.getByTestId('screen-claims').getAttribute('data-state')).toBe('empty'))
    expect(where()).toBe('/merchant/S-0142/app?lang=en&screen=claims')
    expect([current('home'), current('claims'), current('help')]).toEqual([null, 'page', null])
    fireEvent.click(screen.getByTestId('app-tab-help'))
    await screen.findByTestId('screen-help')
    historyBack()
    await screen.findByTestId('screen-claims')
    historyBack()
    await screen.findByTestId('screen-home')
    expect(where()).toBe('/merchant/S-0142/app?lang=en')
  })

  it('does not add a history entry for the tab that is already open', async () => {
    renderStandalone('/merchant/S-0142/app?lang=en', backend)
    await screen.findByTestId('screen-home')
    fireEvent.click(screen.getByTestId('app-tab-claims'))
    await screen.findByTestId('screen-claims')
    fireEvent.click(screen.getByTestId('app-tab-claims'))
    historyBack()
    await screen.findByTestId('screen-home')
    expect(where()).toBe('/merchant/S-0142/app?lang=en')
  })

  it('keeps mock and presenter on every move, in a fixed order', async () => {
    renderStandalone('/merchant/S-0142/app?presenter=1&mock=1&lang=en&junk=x', backend)
    await screen.findByTestId('screen-home')
    fireEvent.click(screen.getByTestId('app-tab-claims'))
    await screen.findByTestId('screen-claims')
    expect(where()).toBe('/merchant/S-0142/app?mock=1&presenter=1&lang=en&screen=claims')
  })

  it('shows Back on a screen below a tab, which leads to the parent; a tab screen has none', async () => {
    renderStandalone('/merchant/S-0142/app?lang=en&screen=receipt&decision=D-000142', backend)
    await screen.findByTestId('screen-receipt')
    expect(current('claims')).toBe('page')
    fireEvent.click(screen.getByTestId('app-back'))
    await screen.findByTestId('screen-claims')
    expect(where()).toBe('/merchant/S-0142/app?lang=en&screen=claims')
    expect(screen.queryByTestId('app-back')).toBeNull()
  })

  it('shows Home for a screen it does not have', async () => {
    renderStandalone('/merchant/S-0142/app?lang=en&screen=nonsense', backend)
    expect((await screen.findByTestId('screen-home')).getAttribute('data-state')).toBe('ready')
  })

  it('opens Settings from the language button once, keeping the language', async () => {
    renderStandalone('/merchant/S-0142/app?lang=en', backend)
    await screen.findByTestId('screen-home')
    fireEvent.click(screen.getByTestId('app-lang-button'))
    await screen.findByTestId('screen-settings')
    expect(where()).toBe('/merchant/S-0142/app?lang=en&screen=settings')
    expect(current('help')).toBe('page')
    fireEvent.click(screen.getByTestId('app-lang-button'))
    historyBack()
    await screen.findByTestId('screen-home')
  })

  it('speaks Hindi by default for Anil, English with lang=en, and labels the language button in the language shown', async () => {
    const hindi = renderStandalone('/merchant/S-0142/app', backend)
    await screen.findByTestId('screen-home')
    expect(screen.getByTestId('app-root').getAttribute('lang')).toBe('hi')
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('छतरी')
    expect(screen.getByTestId('app-lang-button').getAttribute('aria-label')).toBe('भाषा')
    hindi.unmount()
    backend = testBackend()
    renderStandalone('/merchant/S-0142/app?lang=en', backend)
    await screen.findByTestId('screen-home')
    expect(screen.getByTestId('app-lang-button').getAttribute('aria-label')).toBe('Language')
  })

  it('resets to Home when a scenario is loaded', async () => {
    const { api } = renderStandalone('/merchant/S-0142/app?lang=en&screen=claims', backend)
    await screen.findByTestId('screen-claims')
    await waitFor(() => expect(screen.getByTestId('probe-location').getAttribute('data-stream')).toBe('open'))
    await act(async () => void (await api.load('illness')))
    await screen.findByTestId('screen-home')
    expect(where()).toBe('/merchant/S-0142/app?lang=en')
  })

  it('says "Unknown merchant" for a bad id, with no app and no request', async () => {
    renderStandalone('/merchant/bogus/app', backend)
    const message = await screen.findByTestId('app-unknown-merchant')
    expect(message.getAttribute('role')).toBe('alert')
    expect(screen.queryByTestId('app-root')).toBeNull()
  })
})
