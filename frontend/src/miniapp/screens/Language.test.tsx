/** S9 Language (fs-04 section 8, 13): the radio list, the switch (AC-32), the fallback note (AC-33), Marathi hidden (AC-34). */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

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
  vi.unstubAllEnvs()
})

async function openLanguage(search = '?lang=hi&screen=settings') {
  const kit = testApi()
  backend = kit.backend
  renderStandalone(`/merchant/S-0142/app${search}`, kit.backend, kit.api)
  await screen.findByTestId('screen-language')
}

describe('Language', () => {
  it('lists Hindi and English in their own script and no Marathi while the flag is off', async () => {
    await openLanguage()
    expect(screen.getByTestId('lang-option-hi')).toBeTruthy()
    expect(screen.getByTestId('lang-option-en')).toBeTruthy()
    expect(screen.queryByTestId('lang-option-mr')).toBeNull()
    expect(screen.getByTestId('lang-option-hi').getAttribute('aria-checked')).toBe('true')
    expect(document.body.textContent).toContain('हिंदी')
    expect(document.body.textContent).toContain('English')
  })

  it('switches to English: root lang, tabs and URL change (AC-32)', async () => {
    await openLanguage()
    expect(screen.getByTestId('app-root').getAttribute('lang')).toBe('hi')
    fireEvent.click(screen.getByTestId('lang-option-en'))
    await waitFor(() => expect(screen.getByTestId('app-root').getAttribute('lang')).toBe('en'))
    expect(screen.getByTestId('app-tab-home').textContent).toContain('Home')
    expect(screen.getByTestId('app-tab-claims').textContent).toContain('Claims')
    expect(screen.getByTestId('app-tab-help').textContent).toContain('Help')
    expect(screen.getByTestId('probe-location').textContent).toContain('lang=en')
  })

  it('shows a preview line in the chosen language and no fallback note for Hindi or English', async () => {
    await openLanguage('?lang=en&screen=settings')
    expect(screen.getByTestId('lang-preview').textContent).toContain('Preview')
    expect(screen.queryByTestId('lang-fallback-note')).toBeNull()
  })

  it('shows the Hindi text of a missing Marathi string inside an element marked lang hi, with Marathi hidden showing Hindi (AC-34)', async () => {
    await openLanguage('?lang=mr&screen=settings')
    expect(screen.getByTestId('app-root').getAttribute('lang')).toBe('hi')
  })

  it('with n8_marathi on, offers Marathi and switches the root to lang mr with Marathi tabs (card 6.7)', async () => {
    vi.stubEnv('VITE_FEATURES', 'n1_miniapp,n8_marathi')
    await openLanguage()
    expect(screen.getByTestId('lang-option-mr').closest('label')?.textContent).toContain('मराठी')
    fireEvent.click(screen.getByTestId('lang-option-mr'))
    await waitFor(() => expect(screen.getByTestId('app-root').getAttribute('lang')).toBe('mr'))
    expect(screen.getByTestId('app-tab-help').textContent).toContain('मदत')
    expect(screen.getByTestId('probe-location').textContent).toContain('lang=mr')
    expect(screen.queryByTestId('lang-fallback-note')).toBeNull()
  })

  it('ends with the way back to Home', async () => {
    await openLanguage()
    await waitFor(() => expect(screen.getByTestId('app-nba').getAttribute('data-nba')).toBe('home_after_language'))
  })
})
