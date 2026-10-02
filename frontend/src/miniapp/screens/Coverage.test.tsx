/** S2 Coverage explainer (fs-04 section 8): every number read from the rules, every term tappable, no link by viewing (AC-10, AC-11, AC-12). */
import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiClient, ApiError } from '../../api/client'
import type { MockBackend } from '../../mock/backend'
import { testApi } from '../../mock/testkit'
import { renderStandalone } from '../shell/shellKit'

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  window.localStorage.clear()
})
afterEach(() => {
  backend?.dispose()
  vi.restoreAllMocks()
})

type Options = { merchant?: string; at?: string | null; search?: string; scenario?: 'buy_cover'; kit?: ReturnType<typeof testApi> }

async function openCoverage({ merchant = 'S-0142', at = '17:05', search = '?lang=en&screen=coverage', scenario, kit = testApi() }: Options = {}) {
  backend = kit.backend
  if (scenario) await kit.api.load(scenario)
  if (at !== null) await kit.api.seek(at)
  const view = renderStandalone(`/merchant/${merchant}/app${search}`, kit.backend, kit.api)
  await waitFor(() => expect(screen.getByTestId('screen-coverage').getAttribute('data-state')).toBe('ready'))
  return view
}

const text = (id: string) => screen.getByTestId(id).textContent ?? ''
const trigger = (id: string) => within(screen.getByTestId(`coverage-section-${id}`)).getAllByRole('button')[0]
const SECTIONS = ['c2', 'c3', 'c4', 'c5', 'c6', 'c7', 'c10'] as const

describe('the numbers come from the rules (AC-10)', () => {
  it('shows the six figures of your cover in numbers, all read from GET /api/policy', async () => {
    await openCoverage()
    const card = screen.getByTestId('coverage-numbers')
    expect(within(card).getByRole('heading').textContent).toBe('Your cover in numbers')
    for (const figure of ['50%', '₹2,500', '₹1,500', '₹30,000', '7 days', '72 hours', '30 days']) expect(card.textContent).toContain(figure)
    for (const label of ["Chhatri's share of lost sales", 'Daily limit, rain', 'Daily limit, hospital cash', 'Yearly limit', 'Waiting period']) expect(card.textContent).toContain(label)
  })

  it('puts "7 days" in the section on when cover starts, and "10 days" when the rules say 10', async () => {
    await openCoverage()
    expect(text('coverage-section-c5')).toContain('A new cover starts 7 days after you ask')
    expect(text('coverage-section-c5')).toContain('within 72 hours')
    backend.dispose()
    const kit = testApi()
    const policy = await kit.api.policy()
    const rules = policy.rules as { cover: { waiting_period_days: number } }
    vi.spyOn(kit.api, 'policy').mockResolvedValue({ ...policy, rules: { ...policy.rules, cover: { ...rules.cover, waiting_period_days: 10 } } })
    document.body.innerHTML = ''
    await openCoverage({ kit })
    expect(screen.getAllByTestId('coverage-section-c5').at(-1)?.textContent).toContain('A new cover starts 10 days after you ask')
    expect(screen.getAllByTestId('coverage-numbers').at(-1)?.textContent).toContain('10 days')
  })

  it('reads the caps, the share and the limit of the other sections from the rules too', async () => {
    await openCoverage()
    expect(text('coverage-section-c2')).toContain('Chhatri pays 50% of your shop')
    expect(text('coverage-section-c2')).toContain('The most is ₹2,500 a day.')
    expect(text('coverage-section-c2')).toContain('below 50% of the usual level for 3 hours in a row')
    expect(text('coverage-section-c3')).toContain('up to ₹1,500 a day, for up to 3 days')
    expect(text('coverage-section-c4')).toContain('All payouts together stop at ₹30,000 in any 365 days.')
    expect(text('coverage-section-c6')).toContain('The first payment covers 30 days.')
  })
})

describe('the sections', () => {
  it('lists the seven sections with their clause chips, the first one open and the others closed', async () => {
    await openCoverage()
    const chips: Record<string, string> = { c2: 'C2', c3: 'C3', c4: 'C4', c5: 'C5', c6: 'C6', c7: 'C7C8', c10: 'C10' }
    for (const id of SECTIONS) {
      const section = screen.getByTestId(`coverage-section-${id}`)
      const clauses = Array.from(section.querySelectorAll('[data-clause]')).map((node) => node.textContent).join('')
      expect([id, clauses]).toEqual([id, chips[id]])
    }
    expect(trigger('c2').getAttribute('aria-expanded')).toBe('true')
    expect(trigger('c5').getAttribute('aria-expanded')).toBe('false')
    fireEvent.click(trigger('c5'))
    await waitFor(() => expect(trigger('c5').getAttribute('aria-expanded')).toBe('true'))
    fireEvent.click(trigger('c5'))
    await waitFor(() => expect(trigger('c5').getAttribute('aria-expanded')).toBe('false'))
  })

  it('hides a closed section from the page but keeps its words in it', async () => {
    await openCoverage()
    const content = screen.getByTestId('coverage-section-c6').querySelector('[data-slot="accordion-content"]') as HTMLElement
    expect(content.hasAttribute('hidden')).toBe(true)
    expect((screen.getByTestId('coverage-section-c2').querySelector('[data-slot="accordion-content"]') as HTMLElement).hasAttribute('hidden')).toBe(false)
  })

  it('opens the section the link names through the hash, as the next action of a due premium does', async () => {
    await openCoverage({ search: '?lang=en&screen=coverage#c6' })
    expect(trigger('c6').getAttribute('aria-expanded')).toBe('true')
  })

  it('labels each worked example and says it comes from a simulated replay', async () => {
    await openCoverage()
    const example = screen.getByTestId('coverage-example-c2')
    expect(example.textContent).toContain('Example')
    expect(example.textContent).toContain('A tea stall usually sells ₹4,380 on a Tuesday.')
    expect(example.textContent).toContain('Example from a simulated replay')
    expect(text('coverage-example-c5')).toContain('Ramesh asks on Monday 18 August at 18:00. His cover starts on 25 August.')
    expect(text('coverage-example-c6')).toContain('Zone 3 costs ₹14.16 a day, so 30 days is ₹424.80.')
    expect(screen.queryByTestId('coverage-example-c4')).toBeNull()
  })

  it('lists the reasons Chhatri gives when a claim is not paid, and says a person decides what the system is unsure of', async () => {
    await openCoverage()
    const section = screen.getByTestId('coverage-section-c7')
    expect(section.querySelectorAll('li')).toHaveLength(10)
    expect(section.textContent).toContain("Your cover wasn't in force on that day.")
    expect(section.textContent).toContain('That is not a refusal.')
  })

  it('says rain claims need no forms, and that the rules are the demo rules', async () => {
    await openCoverage()
    expect(text('screen-coverage')).toContain('Rain claims need no forms. Hospital cash needs one photo of the slip.')
    expect(text('coverage-rules-note')).toBe('These are the demo rules (pilot-0.1). They are illustrative. A partner insurer would set the real terms.')
  })

  it('draws the page in Hindi with the Hindi section titles', async () => {
    await openCoverage({ search: '?lang=hi&screen=coverage' })
    expect(text('coverage-section-c5')).toContain('कवर कब शुरू होता है')
    expect(text('coverage-section-c5')).toContain('नया कवर माँगने के 7 दिन बाद शुरू होता है')
    expect(text('coverage-numbers')).toContain('7 दिन')
    expect(text('coverage-example-c5')).toContain('25 अगस्त')
  })
})

describe('the jargon lens on the page (AC-11)', () => {
  it('opens a sheet with an example that names 25 August from the waiting period, and returns focus to the term', async () => {
    await openCoverage()
    const term = screen.getByTestId('term-waiting_period')
    expect(term.getAttribute('aria-haspopup')).toBe('dialog')
    fireEvent.click(term)
    const sheet = await screen.findByTestId('jargon-sheet')
    await waitFor(() => expect(screen.getByTestId('jargon-sheet-example').textContent).toContain('25 August'))
    await waitFor(() => expect(document.activeElement).toBe(screen.getByTestId('jargon-sheet-close')))
    fireEvent.keyDown(sheet, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByTestId('jargon-sheet')).toBeNull())
    expect(document.activeElement).toBe(term)
  })

  it('makes every term of the page a button, once each, so the words of each section can be asked about', async () => {
    await openCoverage()
    const ids = Array.from(screen.getByTestId('screen-coverage').querySelectorAll('[data-testid^="term-"]')).map((node) => node.getAttribute('data-testid'))
    expect(new Set(ids).size).toBe(ids.length)
    for (const id of ['waiting_period', 'payout_share', 'daily_cap', 'annual_limit', 'alert', 'expected_day', 'area_drop', 'referred', 'premium', 'prepaid_through', 'settlement', 'edi_holiday', 'rules_version']) {
      expect([id, ids.includes(`term-${id}`)]).toEqual([id, true])
    }
    expect(text('screen-coverage')).toContain('Tap an underlined word to see what it means.')
  })
})

describe('the price line and the payment link (AC-12)', () => {
  it('shows a covered merchant the price of their own cover, as a prototype price', async () => {
    await openCoverage()
    expect(text('coverage-price')).toContain('Your price: ₹18.62 a day.')
    expect(text('coverage-price')).toContain('Prototype price. The real price is not decided yet.')
  })

  it('tells a merchant with no cover that the price shows when they tap Get cover, and sends no payment link by viewing', async () => {
    const post = vi.spyOn(ApiClient.prototype, 'post')
    await openCoverage({ merchant: 'S-0907', at: null, scenario: 'buy_cover', search: '?lang=en&screen=coverage' })
    expect(text('coverage-price')).toBe('You see your price when you tap Get cover.')
    expect(text('coverage-price')).not.toContain('₹')
    expect(post.mock.calls.filter(([path]) => String(path).includes('premium'))).toEqual([])
  })
})

describe('the states', () => {
  it('shows the error state with Retry, and none of the clauses without their numbers, when the rules fail', async () => {
    const kit = testApi()
    const real = kit.api.policy.bind(kit.api)
    let failing = true
    vi.spyOn(kit.api, 'policy').mockImplementation((signal?: AbortSignal) => (failing ? Promise.reject(new ApiError('internal_error', 'boom', 500)) : real(signal)))
    backend = kit.backend
    renderStandalone('/merchant/S-0142/app?lang=en&screen=coverage', kit.backend, kit.api)
    await waitFor(() => expect(screen.getByTestId('screen-coverage').getAttribute('data-state')).toBe('error'))
    expect(text('app-error')).toContain('Error code: internal_error')
    expect(screen.queryByTestId('coverage-section-c5')).toBeNull()
    expect(screen.queryByTestId('app-nba')).toBeNull()
    failing = false
    fireEvent.click(screen.getByTestId('app-error-retry'))
    await waitFor(() => expect(screen.getByTestId('screen-coverage').getAttribute('data-state')).toBe('ready'))
  })

  it('shows skeleton blocks while the rules load', async () => {
    const kit = testApi()
    vi.spyOn(kit.api, 'policy').mockImplementation(() => new Promise(() => undefined))
    backend = kit.backend
    renderStandalone('/merchant/S-0142/app?lang=en&screen=coverage', kit.backend, kit.api)
    const root = await screen.findByTestId('screen-coverage')
    expect(root.getAttribute('data-state')).toBe('loading')
    expect(root.getAttribute('aria-busy')).toBe('true')
    expect(screen.getByTestId('app-skeleton')).toBeTruthy()
  })
})

describe('the next action of the screen', () => {
  it('says get cover for a merchant with no cover', async () => {
    await openCoverage({ merchant: 'S-0907', at: null })
    await waitFor(() => expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('get_cover_from_coverage'))
    fireEvent.click(screen.getByTestId('app-nba-action'))
    await screen.findByTestId('screen-buy')
  })

  it('says see my claims once a claim exists', async () => {
    await openCoverage()
    await waitFor(() => expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('see_claims'))
  })

  it('says back to Home when there is nothing else', async () => {
    await openCoverage({ at: '10:00' })
    await waitFor(() => expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('home_from_coverage'))
  })
})
