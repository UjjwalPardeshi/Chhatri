/**
 * The audit page on a long run (finding: ~2,400 rows rendered slowly): the first paint is the newest page only (one
 * small probe reads the total), "Show earlier entries" loads the page before it, and new entries still arrive live.
 */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MockBackend } from '../mock/backend'
import { testBackend } from '../mock/testkit'
import { renderApp } from '../test/renderApp'
import { AUDIT_PAGE } from './Audit'

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  backend = testBackend()
})
afterEach(() => backend.dispose())

const seqs = () => [...document.querySelectorAll('.audit-table tbody tr.audit-row .audit-row__seq')].map((cell) => Number(cell.textContent?.replace(/\D/g, '')))

function fill(count: number): void {
  for (let i = 0; i < count; i += 1) backend.runtime.record('system', 'test.filler', 'test', `T-${i}`, { i })
}

describe('Audit page', () => {
  it('paints the newest page first, newest on top, and loads earlier entries on demand', async () => {
    fill(AUDIT_PAGE + 50)
    const total = backend.runtime.audit.length
    renderApp('/audit', backend)
    await waitFor(() => expect(seqs()).toHaveLength(AUDIT_PAGE))
    expect(seqs()[0]).toBe(total)
    expect(Math.min(...seqs())).toBe(total - AUDIT_PAGE + 1)
    fireEvent.click(screen.getByRole('button', { name: 'Show earlier entries' }))
    await waitFor(() => expect(seqs()).toHaveLength(total))
    expect(Math.min(...seqs())).toBe(1)
    expect(screen.queryByRole('button', { name: 'Show earlier entries' })).toBeNull()
  })

  it('shows every entry and no "earlier" button on a short run', async () => {
    renderApp('/audit', backend)
    await waitFor(() => expect(seqs()).toHaveLength(backend.runtime.audit.length))
    expect(screen.queryByRole('button', { name: 'Show earlier entries' })).toBeNull()
  })

  it('adds new entries live on top', async () => {
    fill(AUDIT_PAGE + 5)
    renderApp('/audit', backend)
    await waitFor(() => expect(seqs()).toHaveLength(AUDIT_PAGE))
    fill(1)
    await waitFor(() => expect(seqs()[0]).toBe(backend.runtime.audit.length))
  })
})
