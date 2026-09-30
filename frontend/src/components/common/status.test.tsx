/** Error wording and stale content (SPEC §20 "Resilience"). */
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import { AsyncView, errorText, isConnectionError } from './Status'

const NETWORK = new ApiError('NETWORK_ERROR', 'Cannot reach the Chhatri server (Failed to fetch)', 0)
const CONFLICT = new ApiError('CONFLICT', 'Case already decided', 409)

describe('error wording', () => {
  it('reads a connection failure in plain words and keeps other errors exact', () => {
    expect(isConnectionError(NETWORK)).toBe(true)
    expect(isConnectionError(new ApiError('TIMEOUT', 'slow', 0))).toBe(true)
    expect(isConnectionError(CONFLICT)).toBe(false)
    expect(errorText(NETWORK)).toEqual({ text: 'Can’t reach the Chhatri server. Check that it is running, then try again.', showCode: false })
    expect(errorText(CONFLICT)).toEqual({ text: 'Case already decided', showCode: true })
  })

  it('keeps stale content through a network blip with a quiet note, and flags other errors', () => {
    const reload = vi.fn<() => void>()
    const { rerender } = render(
      <AsyncView data="kept" error={NETWORK} loading={false} reload={reload}>
        {(d) => <p>{d}</p>}
      </AsyncView>,
    )
    expect(screen.getByText('kept')).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(reload).toHaveBeenCalled()
    rerender(
      <AsyncView data="kept" error={CONFLICT} loading={false} reload={reload}>
        {(d) => <p>{d}</p>}
      </AsyncView>,
    )
    expect(screen.getByRole('alert').textContent).toContain('[CONFLICT]')
  })

  it('shows the plain words when nothing loaded yet, with the details in the tooltip', () => {
    render(
      <AsyncView data={null} error={NETWORK} loading={false} reload={() => undefined}>
        {() => null}
      </AsyncView>,
    )
    const line = screen.getByText(/Can’t reach the Chhatri server/)
    expect(line.getAttribute('title')).toBe('Cannot reach the Chhatri server (Failed to fetch) [NETWORK_ERROR]')
  })
})
