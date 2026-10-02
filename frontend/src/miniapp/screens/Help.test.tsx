/** S8 Help (fs-04 section 8): rows for coverage, language and about, the glossary chips, and the dispute hint. */
import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MockBackend } from '../../mock/backend'
import { testApi } from '../../mock/testkit'
import { TERM_IDS } from '../glossary'
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

async function openHelp(search = '?lang=en&screen=help') {
  const kit = testApi()
  backend = kit.backend
  await kit.api.seek('17:05')
  renderStandalone(`/merchant/S-0142/app${search}`, kit.backend, kit.api)
  await waitFor(() => expect(screen.getByTestId('screen-help').getAttribute('data-state')).toBe('ready'))
}
const text = (id: string) => screen.getByTestId(id).textContent ?? ''

describe('Help', () => {
  it('shows the always-on rows, and none of the rows whose flag is off', async () => {
    await openHelp()
    expect(text('help-coverage')).toContain('What am I covered for?')
    expect(text('help-language')).toContain('Language')
    expect(text('help-about')).toContain('Prototype. Anil Jadhav and every merchant here are synthetic.')
    for (const id of ['help-ask', 'help-grievances', 'help-consents']) expect(screen.queryByTestId(id)).toBeNull()
  })

  it('explains the SIMULATED, FALLBACK and LIVE badges in the About row', async () => {
    await openHelp()
    const about = screen.getByTestId('help-about')
    for (const mode of ['SIMULATED', 'FALLBACK', 'LIVE']) expect(within(about).getByText(mode).getAttribute('data-mode')).toBe(mode)
    expect(about.textContent).toContain('Demo data. No real money, message or payment moves.')
  })

  it('has one button for every insurance word, and the dispute hint', async () => {
    await openHelp()
    for (const id of TERM_IDS) expect(screen.getByTestId(`term-${id}`)).toBeTruthy()
    expect(text('help-dispute')).toContain('open the claim and tap This is wrong.')
  })

  it('opens the coverage and language screens from its rows', async () => {
    await openHelp()
    fireEvent.click(screen.getByTestId('help-coverage'))
    expect(await screen.findByTestId('screen-coverage')).toBeTruthy()
  })

  it('goes to the language screen', async () => {
    await openHelp()
    fireEvent.click(screen.getByTestId('help-language'))
    expect(await screen.findByTestId('screen-settings')).toBeTruthy()
  })

  it('reads in Hindi', async () => {
    await openHelp('?lang=hi&screen=help')
    expect(text('help-language')).toContain('भाषा')
  })

  it('ends with the global next step', async () => {
    await openHelp()
    await waitFor(() => expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBeTruthy())
  })
})
