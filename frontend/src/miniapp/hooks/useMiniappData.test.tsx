/** The mini-app's data hooks: cover, claims, receipt and rules, each through the strict parser (card 3.8). */
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { MockBackend } from '../../mock/backend'
import { testApi } from '../../mock/testkit'
import { LiveProvider } from '../../state/live'
import { useClaims, useCover, useReceipt } from './useMiniappData'
import { useRules } from './useRules'

let backend: MockBackend
afterEach(() => {
  backend?.dispose()
  vi.restoreAllMocks()
})

async function setup(at = '17:05') {
  const kit = testApi()
  backend = kit.backend
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  await kit.api.seek(at)
  const wrapper = ({ children }: { children: ReactNode }) => (
    <MemoryRouter>
      <LiveProvider api={kit.api} mock>
        {children}
      </LiveProvider>
    </MemoryRouter>
  )
  return { ...kit, wrapper }
}

describe('useCover', () => {
  it('returns Anil\'s cover at 17:05, parsed', async () => {
    const { wrapper } = await setup()
    const { result } = renderHook(() => useCover('S-0142'), { wrapper })
    await waitFor(() => expect(result.current.state).toBe('ready'))
    expect(result.current.data).toMatchObject({ status: 'ACTIVE', premium_per_day_label: '₹18.62', amount_claimed_label: '₹1,380' })
  })

  it('is a contract violation, never a guess, when the body has an unknown field', async () => {
    const { wrapper, api } = await setup()
    vi.spyOn(api, 'cover').mockResolvedValue({ ...(await api.cover('S-0142')), surprise: 1 } as never)
    const { result } = renderHook(() => useCover('S-0142'), { wrapper })
    await waitFor(() => expect(result.current.state).toBe('error'))
    expect(result.current.error?.code).toBe('contract_violation')
    expect(result.current.error?.message).toContain('surprise')
  })
})

describe('useClaims', () => {
  it('returns the claim of Anil, and the empty state for a merchant with no claims', async () => {
    const { wrapper } = await setup()
    const anil = renderHook(() => useClaims('S-0142'), { wrapper })
    await waitFor(() => expect(anil.result.current.state).toBe('ready'))
    expect(anil.result.current.data?.map((c) => c.claim_id)).toEqual(['CL-000142'])
    const ramesh = renderHook(() => useClaims('S-0907'), { wrapper })
    await waitFor(() => expect(ramesh.result.current.state).toBe('empty'))
    expect(ramesh.result.current.data).toEqual([])
  })
})

describe('useReceipt', () => {
  it('returns the receipt of a decision, parsed', async () => {
    const { wrapper } = await setup()
    const { result } = renderHook(() => useReceipt('S-0142', 'D-000142'), { wrapper })
    await waitFor(() => expect(result.current.state).toBe('ready'))
    expect(result.current.data?.decision).toMatchObject({ id: 'D-000142', amount_label: '₹1,380' })
  })

  it('is a not_found error for an unknown decision, and for a link with no decision, without asking the API', async () => {
    const { wrapper, api } = await setup()
    const unknown = renderHook(() => useReceipt('S-0142', 'D-999999'), { wrapper })
    await waitFor(() => expect(unknown.result.current.state).toBe('error'))
    expect(unknown.result.current.error).toMatchObject({ code: 'not_found', status: 404 })
    const spy = vi.spyOn(api, 'receipt')
    const none = renderHook(() => useReceipt('S-0142', null), { wrapper })
    await waitFor(() => expect(none.result.current.state).toBe('error'))
    expect(none.result.current.error?.code).toBe('not_found')
    expect(spy).not.toHaveBeenCalled()
  })
})

describe('useRules', () => {
  it('returns the rule numbers of the policy', async () => {
    const { wrapper } = await setup()
    const { result } = renderHook(() => useRules(), { wrapper })
    await waitFor(() => expect(result.current.state).toBe('ready'))
    expect(result.current.data).toMatchObject({ waiting_period_days: 7, annual_limit_label: '₹30,000', dispute_sla_hours: 24 })
  })
})
