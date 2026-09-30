/**
 * Runtime configuration (binding decision B7). Mock mode = `VITE_MOCK=1` at build/dev time or
 * `?mock=1` in the URL (remembered for the tab so in-app links keep it; `?mock=0` turns it off).
 */

export const MOCK_STORAGE_KEY = 'chhatri.mock'

export type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

function safeStorage(): StorageLike | null {
  try {
    return window.sessionStorage
  } catch (error) {
    console.warn('[config] sessionStorage unavailable', error)
    return null
  }
}

export function isMockMode(search: string, envFlag: string | undefined, storage: StorageLike | null = safeStorage()): boolean {
  if (envFlag === '1') return true
  const param = new URLSearchParams(search).get('mock')
  if (param === '1') {
    storage?.setItem(MOCK_STORAGE_KEY, '1')
    return true
  }
  if (param === '0') {
    storage?.removeItem(MOCK_STORAGE_KEY)
    return false
  }
  return storage?.getItem(MOCK_STORAGE_KEY) === '1'
}
