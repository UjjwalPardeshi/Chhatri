/**
 * Seeking by typed time (finding: "seek outside the window shows a raw developer error"): the form checks HH:MM and the
 * scenario's window before it posts, and says so in Hindi and English; a 422 from the server reads the same way.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import type { ClockState } from '../../api/types'
import { friendlyReplayError, SeekForm, seekProblem } from './SeekForm'

const CLOCK: ClockState = {
  now: '2025-08-19T13:30:00+05:30',
  scenario: 'monsoon',
  scenario_title: 'Monsoon',
  running: false,
  speed: 6,
  start: '2025-08-19T08:00:00+05:30',
  end: '2025-08-19T20:00:00+05:30',
  label: 'x',
}

describe('seekProblem', () => {
  it('accepts a time inside the window, edges included', () => {
    expect(seekProblem('17:00', CLOCK)).toBeNull()
    expect(seekProblem('08:00', CLOCK)).toBeNull()
    expect(seekProblem(' 20:00 ', CLOCK)).toBeNull()
  })

  it('asks for HH:MM, then for a time inside the window', () => {
    expect(seekProblem('5pm', CLOCK)).toEqual({ hi: 'समय HH:MM में लिखें, जैसे 17:00।', en: 'Type the time as HH:MM, for example 17:00.' })
    expect(seekProblem('07:00', CLOCK)).toEqual({ hi: 'समय 08:00 से 20:00 के बीच चुनें।', en: 'Pick a time between 08:00 and 20:00.' })
    expect(seekProblem('20:01', CLOCK)?.en).toBe('Pick a time between 08:00 and 20:00.')
  })
})

describe('SeekForm', () => {
  it('does not post a time outside the window, and says why', () => {
    const onSeek = vi.fn<(to: string) => void>()
    render(<SeekForm clock={CLOCK} busy={false} onSeek={onSeek} />)
    fireEvent.change(screen.getByLabelText('Seek to time (HH:MM)'), { target: { value: '07:00' } })
    fireEvent.click(screen.getByRole('button', { name: 'Seek' }))
    expect(onSeek).not.toHaveBeenCalled()
    expect(screen.getByRole('alert').textContent).toBe('समय 08:00 से 20:00 के बीच चुनें। Pick a time between 08:00 and 20:00.')
    fireEvent.change(screen.getByLabelText('Seek to time (HH:MM)'), { target: { value: '17:00' } })
    fireEvent.click(screen.getByRole('button', { name: 'Seek' }))
    expect(onSeek).toHaveBeenCalledWith('17:00')
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

describe('friendlyReplayError', () => {
  it('reads a seek 422 as the window line, and leaves every other error alone', () => {
    const seek = new ApiError('validation_error', 'invalid request', 422, { to: "outside the scenario's time window" })
    expect(friendlyReplayError(seek, CLOCK)?.en).toBe('Pick a time between 08:00 and 20:00.')
    expect(friendlyReplayError(new ApiError('validation_error', 'invalid request', 422, { minutes: 'beyond the end' }), CLOCK)).toBeNull()
    expect(friendlyReplayError(new ApiError('NETWORK_ERROR', 'x', 0), CLOCK)).toBeNull()
  })
})
