/** URL state of the mini-app (fs-04 section 4.3): `screen`, `claim`, `decision`, `lang`, with `mock` and `presenter` kept. */
import { act, renderHook } from '@testing-library/react'
import { createElement, type ReactNode } from 'react'
import { MemoryRouter, useLocation } from 'react-router'
import { describe, expect, it } from 'vitest'

import { merchantIdFromPath, miniappHref, parseMiniappSearch, useMiniappUrl } from './useMiniappUrl'

const wrapper = (initial: string) =>
  function Wrapper({ children }: { children: ReactNode }) {
    return createElement(MemoryRouter, { initialEntries: [initial] }, children)
  }

describe('parseMiniappSearch', () => {
  it('defaults to Home with nothing else set', () => {
    expect(parseMiniappSearch('')).toEqual({ screen: 'home', claim: null, decision: null, lang: null })
  })

  it('reads the screen, the claim, the decision and the language', () => {
    expect(parseMiniappSearch('?screen=why&decision=D-000142&lang=en')).toEqual({ screen: 'why', claim: null, decision: 'D-000142', lang: 'en' })
    expect(parseMiniappSearch('?screen=claim&claim=CL-000142')).toMatchObject({ screen: 'claim', claim: 'CL-000142' })
  })

  it('an unknown screen shows home, and a screen of another spec stays home until it exists', () => {
    expect(parseMiniappSearch('?screen=settings').screen).toBe('settings')
    expect(parseMiniappSearch('?screen=nope').screen).toBe('home')
    expect(parseMiniappSearch('?screen=ask').screen).toBe('home')
  })

  it('rejects a malformed decision id, claim id or language instead of passing it on', () => {
    expect(parseMiniappSearch('?screen=why&decision=D-12').decision).toBeNull()
    expect(parseMiniappSearch('?screen=why&decision=D-000142%20x').decision).toBeNull()
    expect(parseMiniappSearch('?screen=why&decision=../../x').decision).toBeNull()
    expect(parseMiniappSearch('?screen=claim&claim=CL-1').claim).toBeNull()
    expect(parseMiniappSearch('?lang=fr').lang).toBeNull()
  })
})

describe('miniappHref', () => {
  const PATH = '/merchant/S-0142/app'

  it('keeps mock and presenter on every link, and drops everything else', () => {
    expect(miniappHref(PATH, '?mock=1&presenter=1&junk=1&screen=help', { screen: 'claims' })).toBe(`${PATH}?mock=1&presenter=1&screen=claims`)
    expect(miniappHref(PATH, '?junk=1', { screen: 'claims' })).toBe(`${PATH}?screen=claims`)
  })

  it('leaves the screen out for Home and carries the claim or decision only where it applies', () => {
    expect(miniappHref(PATH, '?mock=1', { screen: 'home' })).toBe(`${PATH}?mock=1`)
    expect(miniappHref(PATH, '', { screen: 'claim', claim: 'CL-000142', decision: 'D-000142' })).toBe(`${PATH}?screen=claim&claim=CL-000142`)
    expect(miniappHref(PATH, '', { screen: 'receipt', decision: 'D-000142', claim: 'CL-000142' })).toBe(`${PATH}?screen=receipt&decision=D-000142`)
    expect(miniappHref(PATH, '', { screen: 'claims', decision: 'D-000142' })).toBe(`${PATH}?screen=claims`)
  })

  it('keeps the language, or sets a new one', () => {
    expect(miniappHref(PATH, '?lang=en&screen=help', { screen: 'claims' })).toBe(`${PATH}?lang=en&screen=claims`)
    expect(miniappHref(PATH, '?lang=en', { screen: 'settings', lang: 'hi' })).toBe(`${PATH}?lang=hi&screen=settings`)
  })

  it('refuses an id that would not parse back', () => {
    expect(() => miniappHref(PATH, '', { screen: 'why', decision: 'D-12' })).toThrow(/decision/)
    expect(() => miniappHref(PATH, '', { screen: 'claim', claim: 'x' })).toThrow(/claim/)
  })
})

describe('merchantIdFromPath', () => {
  it('goes through assertMerchantId and answers null for a bad id', () => {
    expect(merchantIdFromPath('S-0142')).toBe('S-0142')
    expect(merchantIdFromPath('S-142')).toBeNull()
    expect(merchantIdFromPath(undefined)).toBeNull()
  })
})

describe('useMiniappUrl', () => {
  it('tab tap sets screen and Back restores it', () => {
    const { result } = renderHook(() => ({ url: useMiniappUrl(), location: useLocation() }), { wrapper: wrapper('/merchant/S-0142/app?mock=1') })
    expect(result.current.url.screen).toBe('home')
    act(() => result.current.url.go({ screen: 'claims' }))
    expect(result.current.url.screen).toBe('claims')
    expect(result.current.location.search).toBe('?mock=1&screen=claims')
    act(() => result.current.url.back())
    expect(result.current.url.screen).toBe('home')
    expect(result.current.location.search).toBe('?mock=1')
  })

  it('replaces the entry when asked, so Back skips it', () => {
    const { result } = renderHook(() => ({ url: useMiniappUrl(), location: useLocation() }), { wrapper: wrapper('/merchant/S-0142/app') })
    act(() => result.current.url.go({ screen: 'claims' }))
    act(() => result.current.url.go({ screen: 'help' }, { replace: true }))
    expect(result.current.url.screen).toBe('help')
    act(() => result.current.url.back())
    expect(result.current.url.screen).toBe('home')
  })

  it('an unknown screen shows home and a malformed decision id is null', () => {
    const unknown = renderHook(() => useMiniappUrl(), { wrapper: wrapper('/merchant/S-0142/app?screen=bogus') })
    expect(unknown.result.current.screen).toBe('home')
    const bad = renderHook(() => useMiniappUrl(), { wrapper: wrapper('/merchant/S-0142/app?screen=why&decision=D-12') })
    expect(bad.result.current).toMatchObject({ screen: 'why', decision: null })
  })

  it('builds hrefs that keep mock and presenter', () => {
    const { result } = renderHook(() => useMiniappUrl(), { wrapper: wrapper('/merchant/S-0907?mock=1&presenter=1&screen=help') })
    expect(result.current.href({ screen: 'buy' })).toBe('/merchant/S-0907?mock=1&presenter=1&screen=buy')
  })
})
