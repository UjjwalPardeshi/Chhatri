/** Overview homepage "/" (SPEC §20; deck slides 1-13) against the mock backend. */
import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MockBackend } from '../mock/backend'
import { testBackend } from '../mock/testkit'
import { offlineTiles, renderApp } from '../test/renderApp'

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  offlineTiles()
  backend = testBackend()
})
afterEach(() => backend.dispose())

/** The whole deck story renders at once; role queries over it are slow under coverage. */
const SLOW_RENDER_MS = 30_000

const section = (name: string) => screen.getByRole('region', { name })

describe('Overview page', () => {
  it('tells the deck story with the golden numbers and hides the replay controls', async () => {
    renderApp('/', backend)
    expect(await screen.findByRole('heading', { level: 1, name: /Chhatri/ })).toBeTruthy()
    expect(screen.getByText('Merchant insurance where the claim starts itself')).toBeTruthy()
    expect(document.querySelector('.control-bar')).toBeNull()
    const hero = within(section('Chhatri'))
    expect(hero.getByText('अनिल जी, आज भारी बारिश से आपके इलाके की बिक्री 63% गिरी।')).toBeTruthy()
    expect(hero.getByText('₹1,380')).toBeTruthy()
    expect(hero.getByText('No claim needed')).toBeTruthy()

    const problem = within(section('The problem'))
    expect(problem.getByText('30-60 days')).toBeTruthy()
    expect(problem.getByText('Same day')).toBeTruthy()

    const storm = within(section('The storm replay'))
    expect(storm.getByRole('heading', { name: 'Zone 7 · 46 shops' })).toBeTruthy()
    for (const value of ['Red alert from 14:00', '37% of expected for 3 hours', '46 of 46 prepaid', '17:04, with the settlement', '₹58,900 · instalments paused']) {
      expect(storm.getByText(value)).toBeTruthy()
    }
    expect(storm.getByText('312')).toBeTruthy()
    expect(storm.getByText('4 min')).toBeTruthy()
    expect(storm.getByText(/Why Zone 9 got nothing/)).toBeTruthy()

    const journeys = within(section('What the merchant sees'))
    expect(journeys.getAllByTestId('story-phone')).toHaveLength(3)
    expect(journeys.getByText('Sent to a claims officer · case C-2291')).toBeTruthy()

    const humans = within(section('Humans in control'))
    expect(humans.getAllByRole('button', { name: /Run it/ })).toHaveLength(3)
    expect(humans.getByText('Waiting period applies')).toBeTruthy()

    expect(within(section('Roadmap and team')).getByText('Ujjwal Pardeshi')).toBeTruthy()
  }, SLOW_RENDER_MS)

  it('reads the backtest and the integration modes from the API', async () => {
    renderApp('/', backend)
    const proof = within(section('Backtest'))
    expect(await proof.findByText(/^91%/)).toBeTruthy()
    expect(proof.getByText('simulated sales · real Open-Meteo rainfall')).toBeTruthy()
    const tech = section('Technology')
    await waitFor(() => expect(tech.querySelectorAll('[data-mode="SIMULATED"]').length).toBe(15))
    expect(within(tech).getByText('The only layer that can approve a payout')).toBeTruthy()
  })

  it('runs a live test: loads the scenario, seeks and opens the phone', async () => {
    renderApp('/', backend)
    const humans = within(section('Humans in control'))
    fireEvent.click(humans.getAllByRole('button', { name: /Run it/ })[2])
    expect(await screen.findByRole('button', { name: 'Red alert tomorrow. Cover me today.' })).toBeTruthy()
    expect(backend.clock.scenario).toBe('buy_cover')
    expect(backend.clock.label).toBe('Mumbai · buy cover replay · 18:10 · simulated')
  })

  it('replays the storm to 17:05 and opens the live map', async () => {
    renderApp('/', backend)
    fireEvent.click(within(section('The storm replay')).getByRole('button', { name: /Replay the storm to 17:05/ }))
    expect(await screen.findByTestId('live-map')).toBeTruthy()
    expect(backend.clock.label).toBe('Mumbai · monsoon replay · 17:05 · simulated')
    expect(backend.runtime.kpis.shops_paid).toBe(312)
  })

  it('shows the failure next to the journey that could not load', async () => {
    renderApp('/', backend)
    const journeys = within(section('What the merchant sees'))
    await screen.findByText('Merchant insurance where the claim starts itself')
    backend.outage(60_000)
    fireEvent.click(journeys.getByRole('button', { name: /Play it live · illness 11:20/ }))
    expect(await journeys.findByText(/Cannot reach the Chhatri server/)).toBeTruthy()
    expect(within(section('Humans in control')).queryByText(/Cannot reach the Chhatri server/)).toBeNull()
  })

  it('shows a visible error when the backtest cannot load', async () => {
    backend.outage(60_000)
    renderApp('/', backend)
    const proof = within(section('Backtest'))
    expect(await proof.findByText(/Cannot reach the Chhatri server/)).toBeTruthy()
    expect(await within(section('Technology')).findByText('Integration status unavailable')).toBeTruthy()
  })
})
