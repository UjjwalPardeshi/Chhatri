/** The jargon lens (H20, fs-04 section 11): a term is a button, the sheet explains it with an example, and focus is kept (AC-11). */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MockBackend } from '../../mock/backend'
import { testApi } from '../../mock/testkit'
import { LiveProvider } from '../../state/live'
import { MiniappRoot } from '../MiniappRoot'
import { MiniappProvider, useMiniapp } from '../shell/MiniappContext'
import { JargonTerm } from './JargonTerm'

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  window.localStorage.clear()
})
afterEach(() => backend?.dispose())

function Root({ children }: { children: ReactNode }) {
  const { lang } = useMiniapp()
  return <MiniappRoot lang={lang}>{children}</MiniappRoot>
}

function inApp(ui: ReactNode, search = '?lang=en', kit = testApi()) {
  backend = kit.backend
  render(
    <MemoryRouter initialEntries={[`/merchant/S-0142/app${search}`]}>
      <LiveProvider api={kit.api} mock>
        <MiniappProvider merchantId="S-0142">
          <Root>{ui}</Root>
        </MiniappProvider>
      </LiveProvider>
    </MemoryRouter>,
  )
  return kit
}

const term = () => screen.getByTestId('term-waiting_period')
const openSheet = async () => {
  fireEvent.click(term())
  return screen.findByTestId('jargon-sheet')
}

describe('JargonTerm', () => {
  it('is a button that opens a dialog, named in the language shown, with a 44 px target', () => {
    inApp(<JargonTerm id="waiting_period" />)
    expect(term().tagName).toBe('BUTTON')
    expect(term().getAttribute('aria-haspopup')).toBe('dialog')
    expect(term().textContent).toBe('Waiting period')
    expect(term().className).toContain('min-h-11')
  })

  it('takes its words from the sentence it stands in, when it is given them', () => {
    inApp(<JargonTerm id="premium">premium</JargonTerm>)
    expect(screen.getByTestId('term-premium').textContent).toBe('premium')
  })
})

describe('JargonSheet', () => {
  it('opens with the term in both languages, the plain words and an example, and focus on Close', async () => {
    inApp(<JargonTerm id="waiting_period" />)
    const sheet = await openSheet()
    expect(sheet.getAttribute('role')).toBe('dialog')
    expect(within(sheet).getByRole('heading', { level: 2 }).textContent).toBe('Waiting period')
    expect(within(sheet).getByTestId('jargon-sheet-other').textContent).toBe('वेटिंग पीरियड')
    await waitFor(() => expect(sheet.textContent).toContain('A new cover starts 7 days after you ask. Until then it does not pay.'))
    expect(screen.getByTestId('jargon-sheet-example').textContent).toContain('25 August')
    expect(sheet.textContent).toContain('In plain words')
    expect(sheet.textContent).toContain('The policy wording has the exact terms.')
    const close = screen.getByTestId('jargon-sheet-close')
    expect(close.textContent).toBe('Close')
    await waitFor(() => expect(document.activeElement).toBe(close))
  })

  it('draws inside the app root, so it never escapes the phone frame', async () => {
    inApp(<JargonTerm id="waiting_period" />)
    const sheet = await openSheet()
    expect(screen.getByTestId('app-root').contains(sheet)).toBe(true)
  })

  it('keeps focus inside while it is open, closes on Escape and returns focus to the term', async () => {
    inApp(<JargonTerm id="waiting_period" />)
    const sheet = await openSheet()
    const close = screen.getByTestId('jargon-sheet-close')
    await waitFor(() => expect(document.activeElement).toBe(close))
    fireEvent.keyDown(close, { key: 'Tab' })
    fireEvent.keyDown(close, { key: 'Tab', shiftKey: true })
    expect(sheet.contains(document.activeElement)).toBe(true)
    fireEvent.keyDown(sheet, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByTestId('jargon-sheet')).toBeNull())
    expect(document.activeElement).toBe(term())
  })

  it('closes with the Close button and returns focus to the term', async () => {
    inApp(<JargonTerm id="waiting_period" />)
    await openSheet()
    fireEvent.click(screen.getByTestId('jargon-sheet-close'))
    await waitFor(() => expect(screen.queryByTestId('jargon-sheet')).toBeNull())
    expect(document.activeElement).toBe(term())
  })

  it('speaks Hindi large with the English small, and the example in Hindi', async () => {
    inApp(<JargonTerm id="waiting_period" />, '?lang=hi')
    const sheet = await openSheet()
    expect(within(sheet).getByRole('heading', { level: 2 }).textContent).toBe('वेटिंग पीरियड')
    expect(within(sheet).getByTestId('jargon-sheet-other').textContent).toBe('Waiting period')
    await waitFor(() => expect(sheet.textContent).toContain('नया कवर माँगने के 7 दिन बाद शुरू होता है'))
    expect(screen.getByTestId('jargon-sheet-example').textContent).toContain('25 अगस्त')
    expect(screen.getByTestId('jargon-sheet-close').textContent).toBe('बंद करें')
  })

  it('fills the numbers from the rules, so a rules change reaches the lens', async () => {
    const kit = testApi()
    const policy = await kit.api.policy()
    const rules = policy.rules as { cover: { waiting_period_days: number } }
    vi.spyOn(kit.api, 'policy').mockResolvedValue({ ...policy, rules: { ...policy.rules, cover: { ...rules.cover, waiting_period_days: 10 } } })
    inApp(<JargonTerm id="waiting_period" />, '?lang=en', kit)
    const sheet = await openSheet()
    await waitFor(() => expect(sheet.textContent).toContain('A new cover starts 10 days after you ask.'))
    expect(sheet.textContent).not.toContain('{')
  })

  it('never shows a raw placeholder: while the rules load it holds the place, and if they fail it says so', async () => {
    const kit = testApi()
    vi.spyOn(kit.api, 'policy').mockRejectedValue(new Error('boom'))
    inApp(<JargonTerm id="annual_limit" />, '?lang=en', kit)
    fireEvent.click(screen.getByTestId('term-annual_limit'))
    const sheet = await screen.findByTestId('jargon-sheet')
    expect(sheet.textContent).not.toContain('{')
    await waitFor(() => expect(within(sheet).getByTestId('app-error')).toBeTruthy())
    expect(screen.getByTestId('jargon-sheet-close')).toBeTruthy()
  })

  it('explains a term whose example has no number as well', async () => {
    inApp(<JargonTerm id="audit_fingerprint" />)
    fireEvent.click(screen.getByTestId('term-audit_fingerprint'))
    const sheet = await screen.findByTestId('jargon-sheet')
    expect(within(sheet).getByRole('heading', { level: 2 }).textContent).toBe('Audit code')
    expect(screen.getByTestId('jargon-sheet-example').textContent).toContain('"Check the log"')
  })
})
