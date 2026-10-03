/** The language of the app (fs-04 section 13): the options the flags allow, the bound translator, and switching (AC-32, AC-34). */
import { act, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MockBackend } from '../../mock/backend'
import { testApi } from '../../mock/testkit'
import { LiveProvider } from '../../state/live'
import { Copy } from '../lib/copyText'
import { LANG_STORAGE_KEY, MiniappProvider } from '../shell/MiniappContext'
import { Probe } from '../shell/probe'
import { mr as marathi } from '../copy/mr'
import { useLanguage } from './useLanguage'

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  window.localStorage.clear()
})
afterEach(() => {
  backend?.dispose()
  vi.unstubAllEnvs()
})

function wrapperFor(search: string) {
  const kit = testApi()
  backend = kit.backend
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={[`/merchant/S-0142/app${search}`]}>
        <LiveProvider api={kit.api} mock>
          <MiniappProvider merchantId="S-0142">{children}</MiniappProvider>
          <Probe />
        </LiveProvider>
      </MemoryRouter>
    )
  }
}

describe('useLanguage', () => {
  it('offers Hindi and English, and Marathi only while n8_marathi is on', () => {
    const off = renderHook(() => useLanguage(), { wrapper: wrapperFor('?lang=en') })
    expect(off.result.current.languages).toEqual(['hi', 'en'])
    off.unmount()
    vi.stubEnv('VITE_FEATURES', 'n8_marathi')
    const on = renderHook(() => useLanguage(), { wrapper: wrapperFor('?lang=en') })
    expect(on.result.current.languages).toEqual(['hi', 'en', 'mr'])
  })

  it('translates with the language shown, and names each language in its own script', () => {
    const { result } = renderHook(() => useLanguage(), { wrapper: wrapperFor('?lang=hi') })
    expect(result.current.lang).toBe('hi')
    expect(result.current.t('nav.claims')).toBe('दावे')
    expect(result.current.t('app.clock', { time: '17:05' })).toBe('डेमो: 17:05')
  })

  it('switches the language: the URL carries it, the choice is kept, and the words change', async () => {
    const { result } = renderHook(() => useLanguage(), { wrapper: wrapperFor('?lang=hi&screen=settings') })
    act(() => result.current.setLang('en'))
    await waitFor(() => expect(result.current.lang).toBe('en'))
    expect(result.current.t('nav.claims')).toBe('Claims')
    expect(window.localStorage.getItem(LANG_STORAGE_KEY)).toBe('en')
  })

  it('still switches for the session when storage is blocked', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    const { result } = renderHook(() => useLanguage(), { wrapper: wrapperFor('?lang=hi') })
    act(() => result.current.setLang('en'))
    await waitFor(() => expect(result.current.lang).toBe('en'))
  })

  it('says a language is not complete only while Marathi is chosen and some text falls back', () => {
    vi.stubEnv('VITE_FEATURES', 'n8_marathi')
    const mr = renderHook(() => useLanguage(), { wrapper: wrapperFor('?lang=mr') })
    expect(mr.result.current.lang).toBe('mr')
    expect(mr.result.current.fallbackNote).toBe(false)
    mr.unmount()
    const saved = marathi['nav.home']
    delete (marathi as Record<string, string>)['nav.home']
    try {
      const short = renderHook(() => useLanguage(), { wrapper: wrapperFor('?lang=mr') })
      expect(short.result.current.fallbackNote).toBe(true)
      short.unmount()
    } finally {
      ;(marathi as Record<string, string>)['nav.home'] = saved as string
    }
    const hi = renderHook(() => useLanguage(), { wrapper: wrapperFor('?lang=hi') })
    expect(hi.result.current.fallbackNote).toBe(false)
  })
})

describe('Copy', () => {
  it('draws the string in the language shown, with no lang of its own while it is that language', () => {
    const Wrapper = wrapperFor('?lang=hi')
    render(<Copy k="nav.home" data-testid="copy" />, { wrapper: Wrapper })
    const node = screen.getByTestId('copy')
    expect(node.textContent).toBe('होम')
    expect(node.getAttribute('lang')).toBeNull()
  })

  it('puts the language of a string that fell back on the string itself (AC-33)', () => {
    vi.stubEnv('VITE_FEATURES', 'n8_marathi')
    const saved = marathi['nav.home']
    delete (marathi as Record<string, string>)['nav.home']
    try {
      render(<Copy k="nav.home" as="p" data-testid="copy" />, { wrapper: wrapperFor('?lang=mr') })
      const node = screen.getByTestId('copy')
      expect(node.tagName).toBe('P')
      expect(node.textContent).toBe('होम')
      expect(node.getAttribute('lang')).toBe('hi')
    } finally {
      ;(marathi as Record<string, string>)['nav.home'] = saved as string
    }
  })

  it('fills its {placeholders}', () => {
    render(<Copy k="app.clock" params={{ time: '17:05' }} data-testid="copy" />, { wrapper: wrapperFor('?lang=en') })
    expect(screen.getByTestId('copy').textContent).toBe('Demo date and time: 17:05')
  })

  it('is a button label in tests that click it', () => {
    const onClick = vi.fn<() => void>()
    render(
      <button type="button" onClick={onClick}>
        <Copy k="nav.help" />
      </button>,
      { wrapper: wrapperFor('?lang=en') },
    )
    fireEvent.click(screen.getByRole('button', { name: 'Help' }))
    expect(onClick).toHaveBeenCalledTimes(1)
  })
})
