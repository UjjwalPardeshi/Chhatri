/** The static demo banner (screens-and-flows 8, N7): standalone on the mock only, folded away by "Got it" for the tab. */
import { fireEvent, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MockBackend } from '../../mock/backend'
import { testBackend } from '../../mock/testkit'
import { renderStandalone } from './shellKit'
import { STATIC_BANNER_KEY } from './StaticBanner'

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  window.sessionStorage.clear()
  backend = testBackend()
})
afterEach(() => {
  backend.dispose()
  vi.restoreAllMocks()
})

describe('the static demo banner', () => {
  it('says the data is made up, and Got it folds it away for the tab while the SIMULATED badge stays', async () => {
    renderStandalone('/merchant/S-0142/app?lang=en', backend)
    const banner = await screen.findByTestId('app-static-banner')
    expect(banner.textContent).toContain('This is the static demo. It runs in your browser with made-up data. Nothing is sent anywhere.')
    fireEvent.click(screen.getByTestId('app-static-banner-close'))
    expect(screen.queryByTestId('app-static-banner')).toBeNull()
    expect(window.sessionStorage.getItem(STATIC_BANNER_KEY)).toBe('1')
    expect(screen.getByTestId('app-mode-badge').textContent).toBe('SIMULATED')
  })

  it('stays folded once dismissed in this tab', async () => {
    window.sessionStorage.setItem(STATIC_BANNER_KEY, '1')
    renderStandalone('/merchant/S-0142/app?lang=en', backend)
    await screen.findByTestId('screen-home')
    expect(screen.queryByTestId('app-static-banner')).toBeNull()
  })
})
