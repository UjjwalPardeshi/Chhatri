/** The demo clock sheet of the standalone route (screens-and-flows 8, N7): chapters, Play and Pause, back to the start. */
import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MockBackend } from '../../mock/backend'
import { testBackend } from '../../mock/testkit'
import { renderStandalone } from './shellKit'

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  window.localStorage.clear()
  backend = testBackend()
})
afterEach(() => {
  backend.dispose()
  vi.restoreAllMocks()
})

async function openSheet() {
  renderStandalone('/merchant/S-0142/app?lang=en', backend)
  await screen.findByTestId('screen-home')
  await waitFor(() => expect(screen.getByTestId('app-clock').getAttribute('datetime')).not.toBeNull())
  fireEvent.click(screen.getByTestId('app-clock-open'))
  return screen.findByTestId('app-clock-sheet')
}

describe('the demo clock sheet', () => {
  it('opens from the clock and lists the four monsoon chapters, Play and Back to the start', async () => {
    const sheet = await openSheet()
    expect(within(sheet).getByText('Demo date and time')).toBeTruthy()
    expect(within(sheet).getByText('Move the demo clock. The replay is made up.')).toBeTruthy()
    for (const at of ['14:00', '17:00', '17:04', '17:05']) expect(within(sheet).getByTestId(`app-clock-chapter-${at}`)).toBeTruthy()
    expect(within(sheet).getByTestId('app-clock-chapter-17:04').textContent).toBe('Paid 17:04')
    expect(within(sheet).getByTestId('app-clock-play').textContent).toBe('Play')
    expect(within(sheet).getByTestId('app-clock-reset').textContent).toBe('Back to the start')
  })

  it('moves the replay to a chapter, so the paid claim is on Home at once', async () => {
    const sheet = await openSheet()
    fireEvent.click(within(sheet).getByTestId('app-clock-chapter-17:05'))
    await waitFor(() => expect(screen.getByTestId('app-clock').getAttribute('datetime')).toMatch(/T17:05/))
    expect(backend.runtime.nowIso).toMatch(/T17:05/)
  })

  it('plays and pauses the replay, and goes back to the start', async () => {
    const sheet = await openSheet()
    fireEvent.click(within(sheet).getByTestId('app-clock-chapter-17:04'))
    await waitFor(() => expect(backend.runtime.nowIso).toMatch(/T17:04/))
    fireEvent.click(within(sheet).getByTestId('app-clock-play'))
    await waitFor(() => expect(within(sheet).getByTestId('app-clock-play').textContent).toBe('Pause'))
    fireEvent.click(within(sheet).getByTestId('app-clock-play'))
    await waitFor(() => expect(within(sheet).getByTestId('app-clock-play').textContent).toBe('Play'))
    fireEvent.click(within(sheet).getByTestId('app-clock-reset'))
    await waitFor(() => expect(backend.runtime.nowIso).not.toMatch(/T17:0/))
  })
})
