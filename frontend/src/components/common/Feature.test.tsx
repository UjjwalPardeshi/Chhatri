/** The <Feature> gate: a feature that is off is hidden, never half rendered. */
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { Feature } from './Feature'

afterEach(() => vi.unstubAllEnvs())

describe('Feature', () => {
  it('renders its children while the flag is on', () => {
    vi.stubEnv('VITE_FEATURES', 'n2_ask_chhatri')
    render(
      <Feature name="n2_ask_chhatri">
        <p>Ask Chhatri</p>
      </Feature>,
    )
    expect(screen.getByText('Ask Chhatri')).toBeTruthy()
  })

  it('renders nothing while the flag is off, even when another flag is on', () => {
    vi.stubEnv('VITE_FEATURES', 'n1_miniapp')
    const { container } = render(
      <Feature name="n2_ask_chhatri">
        <p>Ask Chhatri</p>
      </Feature>,
    )
    expect(screen.queryByText('Ask Chhatri')).toBeNull()
    expect(container.innerHTML).toBe('')
  })

  it('renders the fallback while the flag is off', () => {
    vi.stubEnv('VITE_FEATURES', '')
    render(
      <Feature name="n6_consents" fallback={<p>Data notice</p>}>
        <p>Consent switches</p>
      </Feature>,
    )
    expect(screen.getByText('Data notice')).toBeTruthy()
    expect(screen.queryByText('Consent switches')).toBeNull()
  })
})
