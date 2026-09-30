/** First paint of each route while its chunk loads (SPEC §20: the Overview opens on navy, no spinner). */
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'

import { RouteFallback } from './App'

describe('RouteFallback', () => {
  it('paints the Overview ground on "/" and a spinner elsewhere', () => {
    const home = render(
      <MemoryRouter initialEntries={['/']}>
        <RouteFallback />
      </MemoryRouter>,
    )
    expect(home.container.querySelector('.ov-fallback')).not.toBeNull()
    expect(home.container.querySelector('.spinner')).toBeNull()
    home.unmount()
    const claims = render(
      <MemoryRouter initialEntries={['/claims']}>
        <RouteFallback />
      </MemoryRouter>,
    )
    expect(claims.container.querySelector('.spinner')).not.toBeNull()
  })
})
