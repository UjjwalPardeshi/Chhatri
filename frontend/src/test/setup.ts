/** Shared vitest setup: DOM cleanup and the few browser APIs happy-dom lacks. */
import { cleanup, configure } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

if (typeof globalThis.ResizeObserver === 'undefined') {
  class ResizeObserverStub {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  Object.assign(globalThis, { ResizeObserver: ResizeObserverStub })
}

/**
 * Lazy pages and the geo JSON load slower under coverage instrumentation and on a busy machine (the
 * slowest Overview tests need ~1.5 s idle, 5-15 s with the CPU shared). Kept below `testTimeout` in
 * vitest.config.ts so a missing element fails with Testing Library's DOM dump, not a bare timeout.
 */
const ASYNC_UTIL_TIMEOUT_MS = 20_000
configure({ asyncUtilTimeout: ASYNC_UTIL_TIMEOUT_MS })
