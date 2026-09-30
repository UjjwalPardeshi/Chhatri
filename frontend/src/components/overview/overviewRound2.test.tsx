/** Overview additions: count-up figures, section rail, USP table (deck slides 1, 10, 11). */
import { act, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { HERO_FIGURES } from '../../content/deck'
import { BENEFITS, USP } from '../../content/deckValue'
import { CountUp, splitCount } from './CountUp'
import { RAIL, SectionRail } from './SectionRail'
import { Usp } from './Usp'

afterEach(() => vi.unstubAllGlobals())

describe('count-up figures', () => {
  it('splits a number from its suffix', () => {
    expect(splitCount('312')).toEqual({ n: 312, suffix: '' })
    expect(splitCount('4 min')).toEqual({ n: 4, suffix: ' min' })
    expect(splitCount('₹1,380')).toBeNull()
    expect(HERO_FIGURES.filter((f) => f.count).map((f) => f.value)).toEqual(['312', '4 min'])
  })

  it('ends on the exact value and keeps it readable throughout', () => {
    vi.useFakeTimers()
    render(<CountUp value="312" />)
    expect(screen.getByText('312')).toBeTruthy()
    act(() => vi.advanceTimersByTime(2_000))
    expect(screen.getByText('312')).toBeTruthy()
    vi.useRealTimers()
  })
})

describe('section rail', () => {
  it('links every deck section and marks the one in the middle of the screen', () => {
    let callback: ((entries: { isIntersecting: boolean; target: Element }[]) => void) | null = null
    class FakeObserver {
      constructor(cb: typeof callback) {
        callback = cb
      }
      observe(): void {}
      disconnect(): void {}
    }
    vi.stubGlobal('IntersectionObserver', FakeObserver)
    render(
      <>
        <section id="ov-storm" />
        <SectionRail />
      </>,
    )
    expect(screen.getAllByRole('link').map((a) => a.getAttribute('href'))).toEqual(RAIL.map((r) => `#${r.id}`))
    act(() => callback?.([{ isIntersecting: true, target: document.getElementById('ov-storm') as Element }]))
    expect(screen.getByRole('link', { name: 'Storm' }).getAttribute('aria-current')).toBe('location')
  })
})

describe('USP and benefits', () => {
  it('renders the deck’s comparison with the Chhatri column marked', () => {
    render(
      <MemoryRouter>
        <Usp />
      </MemoryRouter>,
    )
    expect(screen.getByRole('heading', { name: USP.title })).toBeTruthy()
    expect(screen.getAllByRole('row')).toHaveLength(USP.rows.length + 1)
    expect(document.querySelectorAll('td.usp__ours')).toHaveLength(USP.rows.length)
    expect(screen.getByText(USP.caption)).toBeTruthy()
    expect(BENEFITS.map((b) => b.who)).toEqual(['Merchants', 'Insurer', 'Paytm'])
  })
})
