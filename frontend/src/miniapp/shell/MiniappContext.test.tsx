/** The shell's shared context: language resolution (fs-04 section 13) and the next-best slot (section 12). */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState, type ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MockBackend } from '../../mock/backend'
import { testApi } from '../../mock/testkit'
import { LiveProvider } from '../../state/live'
import { LANG_STORAGE_KEY, MiniappProvider, resolveLang, useMiniapp } from './MiniappContext'
import { NextBestBar, useNextBestAction } from './NextBestBar'
import { Probe } from './probe'

describe('resolveLang', () => {
  const none = { url: null, stored: null, merchant: null, marathi: false }

  it('takes the URL first, then the stored choice, then the merchant language, then Hindi', () => {
    expect(resolveLang({ url: 'en', stored: 'hi', merchant: 'hi', marathi: false })).toBe('en')
    expect(resolveLang({ ...none, stored: 'en', merchant: 'hi' })).toBe('en')
    expect(resolveLang({ ...none, merchant: 'en' })).toBe('en')
    expect(resolveLang(none)).toBe('hi')
  })

  it('ignores a merchant language the app does not have', () => {
    expect(resolveLang({ ...none, merchant: 'ta' })).toBe('hi')
    expect(resolveLang({ ...none, merchant: null })).toBe('hi')
  })

  it('shows Hindi in place of Marathi while n8_marathi is off, and Marathi once it is on', () => {
    expect(resolveLang({ ...none, url: 'mr' })).toBe('hi')
    expect(resolveLang({ ...none, merchant: 'mr' })).toBe('hi')
    expect(resolveLang({ ...none, url: 'mr', marathi: true })).toBe('mr')
  })
})

let backend: MockBackend
beforeEach(() => {
  window.localStorage.clear()
})
afterEach(() => {
  backend?.dispose()
  vi.restoreAllMocks()
  vi.unstubAllEnvs()
})

function inApp(children: ReactNode, search = '') {
  const kit = testApi()
  backend = kit.backend
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  return render(
    <MemoryRouter initialEntries={[`/merchant/S-0142/app${search}`]}>
      <LiveProvider api={kit.api} mock>
        <MiniappProvider merchantId="S-0142">{children}</MiniappProvider>
        <Probe />
      </LiveProvider>
    </MemoryRouter>,
  )
}

function LangProbe() {
  const { lang, setLang, merchant } = useMiniapp()
  return (
    <div>
      <output data-testid="lang">{lang}</output>
      <output data-testid="merchant-language">{merchant.data?.language ?? ''}</output>
      <button type="button" onClick={() => setLang('en')}>to english</button>
      <button type="button" onClick={() => setLang('mr')}>to marathi</button>
    </div>
  )
}

describe('language in the provider', () => {
  it('is the merchant language with nothing chosen, and the chosen one after setLang, kept in the URL and the browser', async () => {
    inApp(<LangProbe />)
    await waitFor(() => expect(screen.getByTestId('merchant-language').textContent).not.toBe(''))
    expect(screen.getByTestId('lang').textContent).toBe(screen.getByTestId('merchant-language').textContent)
    fireEvent.click(screen.getByRole('button', { name: 'to english' }))
    await waitFor(() => expect(screen.getByTestId('lang').textContent).toBe('en'))
    expect(screen.getByTestId('probe-location').textContent).toContain('lang=en')
    expect(window.localStorage.getItem(LANG_STORAGE_KEY)).toBe('en')
  })

  it('reads the stored choice when the URL has none, and the URL beats it', async () => {
    window.localStorage.setItem(LANG_STORAGE_KEY, 'en')
    const first = inApp(<LangProbe />)
    expect(screen.getByTestId('lang').textContent).toBe('en')
    first.unmount()
    inApp(<LangProbe />, '?lang=hi')
    expect(screen.getByTestId('lang').textContent).toBe('hi')
  })

  it('still switches when the browser blocks storage', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError')
    })
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError')
    })
    inApp(<LangProbe />)
    fireEvent.click(screen.getByRole('button', { name: 'to english' }))
    await waitFor(() => expect(screen.getByTestId('lang').textContent).toBe('en'))
  })

  it('keeps Marathi as Hindi while the flag is off', () => {
    inApp(<LangProbe />, '?lang=mr')
    expect(screen.getByTestId('lang').textContent).toBe('hi')
  })

  it('shows Marathi when n8_marathi is on', () => {
    vi.stubEnv('VITE_FEATURES', 'n8_marathi')
    inApp(<LangProbe />, '?lang=mr')
    expect(screen.getByTestId('lang').textContent).toBe('mr')
  })
})

function Registers({ id = 'rule-a', label = 'One sentence.', onAction }: { id?: string; label?: string; onAction: () => void }) {
  useNextBestAction({ id, label, actionLabel: 'Do it', onAction })
  return null
}

function Toggle({ onAction }: { onAction: () => void }) {
  const [on, setOn] = useState(true)
  return (
    <>
      <button type="button" onClick={() => setOn((value) => !value)}>toggle</button>
      {on ? <Registers onAction={onAction} /> : null}
    </>
  )
}

describe('next-best bar', () => {
  it('is absent until a screen registers an action, with no empty strip', () => {
    inApp(<NextBestBar />)
    expect(screen.queryByTestId('app-nba')).toBeNull()
  })

  it('shows the sentence and the button, tagged with the rule id, and runs the latest handler', () => {
    const first = vi.fn<() => void>()
    const second = vi.fn<() => void>()
    const view = inApp(
      <>
        <Registers onAction={first} />
        <NextBestBar />
      </>,
    )
    const bar = screen.getByTestId('app-nba')
    expect(bar.getAttribute('data-nba')).toBe('rule-a')
    expect(bar.textContent).toContain('One sentence.')
    view.rerender(
      <MemoryRouter initialEntries={['/merchant/S-0142/app']}>
        <LiveProvider api={testApi(backend).api} mock>
          <MiniappProvider merchantId="S-0142">
            <Registers onAction={second} />
            <NextBestBar />
          </MiniappProvider>
        </LiveProvider>
      </MemoryRouter>,
    )
    fireEvent.click(screen.getByTestId('app-nba-action'))
    expect(first).toHaveBeenCalledTimes(0)
    expect(second).toHaveBeenCalledTimes(1)
  })

  it('goes away when the screen that registered it unmounts', () => {
    inApp(
      <>
        <Toggle onAction={() => undefined} />
        <NextBestBar />
      </>,
    )
    expect(screen.getByTestId('app-nba')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'toggle' }))
    expect(screen.queryByTestId('app-nba')).toBeNull()
  })

  it('needs the network: the button is disabled offline, with the reason', () => {
    vi.spyOn(window.navigator, 'onLine', 'get').mockReturnValue(false)
    const onAction = vi.fn<() => void>()
    inApp(
      <>
        <Registers onAction={onAction} />
        <NextBestBar />
      </>,
      '?lang=en',
    )
    const button = screen.getByTestId('app-nba-action') as HTMLButtonElement
    expect(button.disabled).toBe(true)
    fireEvent.click(button)
    expect(onAction).not.toHaveBeenCalled()
    expect(screen.getByText('This needs the internet. Please try again when you are online.')).toBeTruthy()
  })

  it('comes back online without a reload', async () => {
    const spy = vi.spyOn(window.navigator, 'onLine', 'get').mockReturnValue(false)
    inApp(
      <>
        <Registers onAction={() => undefined} />
        <NextBestBar />
      </>,
    )
    expect((screen.getByTestId('app-nba-action') as HTMLButtonElement).disabled).toBe(true)
    spy.mockReturnValue(true)
    act(() => void window.dispatchEvent(new Event('online')))
    await waitFor(() => expect((screen.getByTestId('app-nba-action') as HTMLButtonElement).disabled).toBe(false))
  })
})
