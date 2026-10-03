/** The price on the landing page links to the pricing simulator only while h24_whatif is on. */
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { BusinessSection } from './BusinessSection'

afterEach(() => vi.unstubAllEnvs())

function renderSection() {
  render(
    <MemoryRouter>
      <BusinessSection />
    </MemoryRouter>,
  )
}

describe('the price on the landing page', () => {
  it('has no simulator link while h24_whatif is off', () => {
    vi.stubEnv('VITE_FEATURES', '')
    renderSection()
    expect(screen.getByText('What it costs a merchant')).toBeTruthy()
    expect(screen.queryByRole('link', { name: 'Try the pricing simulator' })).toBeNull()
  })

  it('links to the simulator at the end of the Backtest page with the flag', () => {
    vi.stubEnv('VITE_FEATURES', 'h24_whatif')
    renderSection()
    const link = screen.getByRole('link', { name: 'Try the pricing simulator' })
    expect(link.getAttribute('href')).toBe('/backtest#pricing')
    expect(link.className).toBe('lp-price__link')
  })
})
