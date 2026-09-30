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

/** Lazy pages and the geo JSON load slower under coverage instrumentation. */
const ASYNC_UTIL_TIMEOUT_MS = 5_000
configure({ asyncUtilTimeout: ASYNC_UTIL_TIMEOUT_MS })
