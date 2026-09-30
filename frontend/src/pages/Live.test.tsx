/** Live map page against the mock monsoon replay (SPEC §20, deck slide 6). */
import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { MockBackend } from '../mock/backend'
import { testBackend } from '../mock/testkit'
import { offlineTiles, renderApp } from '../test/renderApp'
import { rebuildLabel } from './Live'

let backend: MockBackend
afterEach(() => backend.dispose())

describe('Live map page', () => {
  it('shows the golden monsoon numbers at 17:05', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    offlineTiles()
    backend = testBackend()
    backend.seek('17:05')
    renderApp('/live', backend)
    const map = await screen.findByTestId('live-map')
    await waitFor(() => expect(map.dataset.tiles).toBe('fallback'))
    expect(await screen.findByText('Zone 7 · 46 shops')).toBeTruthy()
    expect(screen.getByText('Basemap offline · wards shown')).toBeTruthy()
    await waitFor(() => expect(document.querySelector('.pin__card')?.textContent).toContain('₹1,380 paid · 17:04'))
    const kpis = document.querySelector('[data-kpi="zones"]')
    expect(kpis?.textContent).toContain('3')
    expect(within(document.body).getByText(/Why Zone 9 got nothing/)).toBeTruthy()
  })

  it('names the rebuild a slow replay action is doing', () => {
    expect(rebuildLabel('load')).toBe('Loading the replay…')
    expect(rebuildLabel('seek')).toBe('Moving the replay clock…')
    expect(rebuildLabel('reset')).toBe('Moving the replay clock…')
    expect(rebuildLabel('play')).toBeNull()
    expect(rebuildLabel(null)).toBeNull()
  })
})
