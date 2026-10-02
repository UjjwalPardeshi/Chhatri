/** Presenter mode in the console (fs-08 section 12): the header button, the key list, the shortcuts and the "More" fold. */
import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MockBackend } from '../../mock/backend'
import { testBackend } from '../../mock/testkit'
import { PRESENTER_STORAGE_KEY } from '../../state/presenter'
import { SLOW_PREF_KEY } from '../../state/useSlowNearPayout'
import { offlineTiles, renderApp } from '../../test/renderApp'

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

const clockText = () => document.querySelector('.clock-label')?.textContent ?? ''
const frame = () => document.querySelector('.app') as HTMLElement
const press = (name: string, target: Element = document.body) => fireEvent.keyDown(target, { key: name })
const flagOn = () => vi.stubEnv('VITE_FEATURES', 'console_polish')

async function renderLive(entry = '/live') {
  const view = renderApp(entry, backend)
  await waitFor(() => expect(clockText()).toContain('08:00'))
  return view
}

describe('with the console_polish flag off', () => {
  it('shows no Present button, no key list and no mode, and the keys do nothing', async () => {
    await renderLive('/live?presenter=1')
    expect(screen.queryByRole('button', { name: 'Present' })).toBeNull()
    expect(frame().dataset.presenter).toBeUndefined()
    press('2')
    press('?')
    expect(screen.queryByRole('region', { name: 'Presenter keys' })).toBeNull()
    expect(clockText()).toContain('08:00')
  })
})

describe('the Present button', () => {
  it('sits in the header with aria-pressed, and the word does not change', async () => {
    flagOn()
    await renderLive()
    const button = screen.getByRole('button', { name: 'Present' })
    expect(within(document.querySelector('.app-header') as HTMLElement).getByRole('button', { name: 'Present' })).toBe(button)
    expect(button.getAttribute('aria-pressed')).toBe('false')
    expect(frame().dataset.presenter).toBeUndefined()
    fireEvent.click(button)
    expect(button.getAttribute('aria-pressed')).toBe('true')
    expect(button.textContent).toBe('Present')
    expect(frame().dataset.presenter).toBe('on')
    expect(window.sessionStorage.getItem(PRESENTER_STORAGE_KEY)).toBe('1')
    fireEvent.click(button)
    expect(button.getAttribute('aria-pressed')).toBe('false')
    expect(frame().dataset.presenter).toBeUndefined()
  })

  it('gives the focus back to the page after a mouse click, so the next Space plays instead of pressing the button again', async () => {
    flagOn()
    await renderLive()
    const button = screen.getByRole('button', { name: 'Present' })
    button.focus()
    fireEvent.click(button, { detail: 1 })
    expect(document.activeElement).not.toBe(button)
    fireEvent.click(button)
    button.focus()
    fireEvent.click(button, { detail: 0 })
    expect(document.activeElement).toBe(button)
  })

  it('starts on with ?presenter=1, and the honest labels stay on screen', async () => {
    flagOn()
    await renderLive('/live?presenter=1')
    expect(screen.getByRole('button', { name: 'Present' }).getAttribute('aria-pressed')).toBe('true')
    expect(frame().dataset.presenter).toBe('on')
    expect(screen.getByText('Mock data')).toBeTruthy()
    expect(screen.getByText(/Sales, alerts, KYC, payouts, lender and Soundbox are simulated/)).toBeTruthy()
    expect(screen.getByRole('button', { name: /simulated/ })).toBeTruthy()
  })
})

describe('the key list', () => {
  it('has a Keys button only while the mode is on, and lists the shortcuts without W', async () => {
    flagOn()
    await renderLive()
    expect(screen.queryByRole('button', { name: 'Keys' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Present' }))
    const keys = screen.getByRole('button', { name: 'Keys' })
    expect(keys.closest('.control-bar')).toBeTruthy()
    expect(keys.getAttribute('aria-expanded')).toBe('false')
    fireEvent.click(keys)
    expect(keys.getAttribute('aria-expanded')).toBe('true')
    const list = screen.getByRole('region', { name: 'Presenter keys' })
    expect(within(list).getAllByRole('term').map((t) => t.textContent)).toEqual(['P', 'Space', '1 to 4', 'S', '?', 'Esc'])
    expect(list.textContent).not.toMatch(/what-if/i)
    fireEvent.click(keys)
    expect(screen.queryByRole('region', { name: 'Presenter keys' })).toBeNull()
  })

  it('opens with ? and closes with Esc', async () => {
    flagOn()
    await renderLive('/live?presenter=1')
    press('?')
    expect(screen.getByRole('region', { name: 'Presenter keys' })).toBeTruthy()
    press('Escape')
    expect(screen.queryByRole('region', { name: 'Presenter keys' })).toBeNull()
  })
})

describe('the shortcuts', () => {
  it('do nothing while presenter mode is off (AC-PM-02)', async () => {
    flagOn()
    await renderLive()
    press('1')
    press('2')
    press(' ')
    press('s')
    await new Promise((resolve) => setTimeout(resolve, 150))
    expect(clockText()).toContain('08:00')
    expect(backend.clock.running).toBe(false)
    expect(window.localStorage.getItem(SLOW_PREF_KEY)).toBeNull()
  })

  it('jump to chapter 2 of the monsoon, a minute before it, as clicking the tick does (AC-PM-03)', async () => {
    flagOn()
    await renderLive('/live?presenter=1')
    press('2')
    await waitFor(() => expect(clockText()).toContain('16:59'))
    press('1')
    await waitFor(() => expect(clockText()).toContain('13:59'))
    press('4')
    await waitFor(() => expect(clockText()).toContain('17:04'))
  })

  it('ignore a chapter the scenario does not have', async () => {
    flagOn()
    await renderLive('/live?presenter=1')
    fireEvent.change(screen.getByRole('combobox', { name: 'Scenario' }), { target: { value: 'illness' } })
    await waitFor(() => expect(clockText()).toContain('illness replay'))
    await waitFor(() => expect((screen.getByRole('combobox', { name: 'Scenario' }) as HTMLSelectElement).disabled).toBe(false))
    const before = clockText()
    press('3')
    await new Promise((resolve) => setTimeout(resolve, 150))
    expect(clockText()).toBe(before)
    press('1')
    await waitFor(() => expect(clockText()).toContain('11:19'))
  })

  it('play and pause on Space, unless a button has focus', async () => {
    flagOn()
    await renderLive('/live?presenter=1')
    press(' ')
    await waitFor(() => expect(backend.clock.running).toBe(true))
    press(' ')
    await waitFor(() => expect(backend.clock.running).toBe(false))
    press(' ', screen.getByRole('button', { name: 'Reset' }))
    await new Promise((resolve) => setTimeout(resolve, 150))
    expect(backend.clock.running).toBe(false)
  })

  it('switch "Slow near payout" on S', async () => {
    flagOn()
    await renderLive('/live?presenter=1')
    const slow = screen.getAllByRole('checkbox', { name: 'Slow near payout' })[0] as HTMLInputElement
    expect(slow.checked).toBe(true)
    press('s')
    await waitFor(() => expect(slow.checked).toBe(false))
    expect(window.localStorage.getItem(SLOW_PREF_KEY)).toBe('0')
    press('S')
    await waitFor(() => expect(slow.checked).toBe(true))
  })

  it('are ignored while the focus is in the seek box, and P turns the mode off', async () => {
    flagOn()
    await renderLive('/live?presenter=1')
    const seek = screen.getByRole('textbox', { name: 'Seek to time (HH:MM)' })
    press('2', seek)
    press('?', seek)
    press('p', seek)
    await new Promise((resolve) => setTimeout(resolve, 150))
    expect(clockText()).toContain('08:00')
    expect(screen.queryByRole('region', { name: 'Presenter keys' })).toBeNull()
    expect(frame().dataset.presenter).toBe('on')
    press('p')
    expect(frame().dataset.presenter).toBeUndefined()
    expect(window.sessionStorage.getItem(PRESENTER_STORAGE_KEY)).toBeNull()
  })
})

describe('quiet controls', () => {
  it('keep the "More" menu markup the phone layout uses: a toggle and a menu that Esc closes', async () => {
    flagOn()
    await renderLive('/live?presenter=1')
    const more = screen.getByRole('button', { name: 'More replay controls' })
    const menu = document.getElementById('transport-more') as HTMLElement
    expect(menu.dataset.open).toBe('false')
    expect(within(menu).getByRole('combobox', { name: 'Speed' })).toBeTruthy()
    expect(within(menu).getByRole('textbox', { name: 'Seek to time (HH:MM)' })).toBeTruthy()
    for (const name of ['+1 min', '+15 min', '+1 h', 'Seek', 'Reset']) expect(within(menu).getByRole('button', { name })).toBeTruthy()
    fireEvent.click(more)
    expect(menu.dataset.open).toBe('true')
    press('Escape')
    expect(menu.dataset.open).toBe('false')
    expect(more.getAttribute('aria-expanded')).toBe('false')
  })

  it('leave the scenario picker, the clock, Play, the scrubber and "Slow near payout" outside the menu', async () => {
    flagOn()
    await renderLive('/live?presenter=1')
    const menu = document.getElementById('transport-more') as HTMLElement
    expect(within(menu).queryByRole('combobox', { name: 'Scenario' })).toBeNull()
    expect(within(menu).queryByRole('button', { name: 'Play' })).toBeNull()
    expect(menu.contains(document.querySelector('.clock-label'))).toBe(false)
    expect(menu.contains(document.querySelector('.scrubber'))).toBe(false)
    expect(document.querySelector('.slow-toggle--bar')).toBeTruthy()
    expect(menu.contains(document.querySelector('.slow-toggle--bar'))).toBe(false)
  })
})
