/** Count-up figures on the landing page's proof strip (SPEC §17.2 golden numbers). */
import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { REPLAY_FIGURES } from '../landing/content'
import { CountUp, splitCount } from './CountUp'

afterEach(() => vi.unstubAllGlobals())

describe('count-up figures', () => {
  it('splits a number from its suffix', () => {
    expect(splitCount('312')).toEqual({ n: 312, suffix: '' })
    expect(splitCount('4 min')).toEqual({ n: 4, suffix: ' min' })
    expect(splitCount('₹1,380')).toBeNull()
    expect(REPLAY_FIGURES.filter((f) => f.count).map((f) => f.value)).toEqual(['4 min', '312'])
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
