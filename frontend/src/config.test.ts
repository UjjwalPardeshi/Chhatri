/** Mock-mode switch (binding decision B7). */
import { describe, expect, it } from 'vitest'

import { isMockMode, MOCK_STORAGE_KEY, type StorageLike } from './config'

function memory(): StorageLike & { data: Map<string, string> } {
  const data = new Map<string, string>()
  return { data, getItem: (k) => data.get(k) ?? null, setItem: (k, v) => void data.set(k, v), removeItem: (k) => void data.delete(k) }
}

describe('isMockMode', () => {
  it('is on with VITE_MOCK=1 regardless of the URL', () => {
    expect(isMockMode('?mock=0', '1', memory())).toBe(true)
  })

  it('remembers ?mock=1 for the tab and forgets it with ?mock=0', () => {
    const storage = memory()
    expect(isMockMode('', undefined, storage)).toBe(false)
    expect(isMockMode('?mock=1', undefined, storage)).toBe(true)
    expect(storage.data.get(MOCK_STORAGE_KEY)).toBe('1')
    expect(isMockMode('?x=1', '0', storage)).toBe(true)
    expect(isMockMode('?mock=0', undefined, storage)).toBe(false)
    expect(isMockMode('', undefined, storage)).toBe(false)
  })

  it('works without storage and falls back to sessionStorage by default', () => {
    expect(isMockMode('?mock=1', undefined, null)).toBe(true)
    expect(isMockMode('', undefined, null)).toBe(false)
    window.sessionStorage.removeItem(MOCK_STORAGE_KEY)
    expect(isMockMode('', undefined)).toBe(false)
  })
})
