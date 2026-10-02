/**
 * Mock sessions and stubs for the claim screens' tests (card 3.10). `session` puts the mock backend at a scenario and a
 * replay time, with the officer token on the kit's own client so a test can play the officer. The stubs answer one
 * route with a fixture and let the real mock answer everything else, so a screen is tested through the real client.
 */
import { vi } from 'vitest'

import { ApiClient } from '../api/client'
import type { ClaimItem, ScenarioName } from '../api/types'
import { MOCK_OFFICER_TOKEN } from '../mock/fixtures'
import { testApi } from '../mock/testkit'

export async function session(scenario: ScenarioName, at: string) {
  const kit = testApi()
  kit.client.setOfficerToken(MOCK_OFFICER_TOKEN)
  await kit.api.load(scenario)
  await kit.api.seek(at)
  return kit
}

/** A hospital-cash claim sent to a claims officer: the mismatched slip of the `illness_mismatch` scenario. */
export async function referredSession() {
  const kit = await session('illness_mismatch', '11:20')
  await kit.api.sendSampleSlip('S-0142', 'mismatch_admission_slip.png')
  return kit
}

const TOTAL_META = (count: number) => ({ total: count, limit: count, offset: 0 })

/** The claims route answers with these items, as the API would. */
export function stubClaims(items: readonly ClaimItem[]): void {
  const real = ApiClient.prototype.list
  vi.spyOn(ApiClient.prototype, 'list').mockImplementation(function (this: ApiClient, path: string, signal?: AbortSignal) {
    if (path.endsWith('/claims')) return Promise.resolve({ items: structuredClone(items), meta: TOTAL_META(items.length) }) as never
    return real.call(this, path, signal)
  })
}

/** The receipt route answers with this body (a test changes a copy of a real receipt). */
export function stubReceipt(body: unknown): void {
  const real = ApiClient.prototype.get
  vi.spyOn(ApiClient.prototype, 'get').mockImplementation(function (this: ApiClient, path: string, signal?: AbortSignal) {
    if (path.endsWith('/receipt')) return Promise.resolve(structuredClone(body)) as never
    return real.call(this, path, signal)
  })
}
