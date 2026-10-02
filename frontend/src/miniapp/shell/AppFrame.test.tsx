/** The frame on the merchant page (fs-04 4.1): the console's phone bezel around the app, and a link to the full screen. */
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MockBackend } from '../../mock/backend'
import { testApi } from '../../mock/testkit'
import { LiveProvider } from '../../state/live'
import AppFrame from './AppFrame'
import { Probe } from './probe'

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  window.localStorage.clear()
})
afterEach(() => {
  backend.dispose()
  vi.restoreAllMocks()
})

function renderFrame(search: string) {
  const kit = testApi()
  backend = kit.backend
  return render(
    <MemoryRouter initialEntries={[`/merchant/S-0142${search}`]}>
      <LiveProvider api={kit.api} mock>
        <AppFrame merchantId="S-0142" />
        <Probe />
      </LiveProvider>
    </MemoryRouter>,
  )
}

const fullscreen = () => screen.getByTestId('app-open-fullscreen').getAttribute('href')

describe('AppFrame', () => {
  it('is a labelled phone bezel with the app inside it, and `phone` is the only console class it uses', async () => {
    renderFrame('?lang=en')
    const frame = await screen.findByTestId('app-frame')
    expect(frame.tagName).toBe('SECTION')
    expect(frame.getAttribute('aria-label')).toBe('Chhatri app, simulated')
    expect(frame.classList.contains('phone')).toBe(true)
    const root = await screen.findByTestId('app-root')
    expect(frame.contains(root)).toBe(true)
    expect(root.classList.contains('miniapp')).toBe(true)
    expect(root.closest('.phone')).toBe(frame)
    expect(root.querySelector('.phone')).toBeNull()
    expect(frame.querySelector('.miniapp .miniapp')).toBeNull()
  })

  it('leaves the page landmarks to the console: no second main and no second h1 inside the frame', async () => {
    renderFrame('?lang=en')
    const frame = await screen.findByTestId('app-frame')
    await screen.findByTestId('screen-home')
    expect(frame.querySelector('main')).toBeNull()
    expect(frame.querySelector('h1')).toBeNull()
    expect(frame.querySelector('h2')?.textContent).toBe('Your cover')
  })

  it('links to the full screen with mock, presenter, language and the open screen kept', async () => {
    renderFrame('?mock=1&presenter=1&lang=en&screen=claims')
    await screen.findByTestId('screen-claims')
    expect(fullscreen()).toBe('/merchant/S-0142/app?mock=1&presenter=1&lang=en&screen=claims')
    expect(screen.getByTestId('app-open-fullscreen').textContent).toBe('Open full screen')
  })

  it('opens the same receipt full size, and follows the app as it moves', async () => {
    renderFrame('?lang=en&screen=receipt&decision=D-000142')
    await screen.findByTestId('screen-receipt')
    expect(fullscreen()).toBe('/merchant/S-0142/app?lang=en&screen=receipt&decision=D-000142')
    fireEvent.click(screen.getByTestId('app-tab-help'))
    await screen.findByTestId('screen-help')
    expect(fullscreen()).toBe('/merchant/S-0142/app?lang=en&screen=help')
    fireEvent.click(screen.getByTestId('app-tab-home'))
    await screen.findByTestId('screen-home')
    expect(fullscreen()).toBe('/merchant/S-0142/app?lang=en')
  })

  it('moves by the query string of the merchant page, and its path stays put', async () => {
    renderFrame('?lang=en')
    await screen.findByTestId('screen-home')
    fireEvent.click(screen.getByTestId('app-tab-claims'))
    await screen.findByTestId('screen-claims')
    expect(screen.getByTestId('probe-location').textContent).toBe('/merchant/S-0142?lang=en&screen=claims')
  })

  it('labels the link in the language shown', async () => {
    renderFrame('')
    await screen.findByTestId('screen-home')
    expect(screen.getByTestId('app-open-fullscreen').textContent).toBe('पूरी स्क्रीन पर खोलें')
  })
})
