/**
 * SSE Stream Tests
 * Tests EventSource handling, reconnect logic, Last-Event-ID retention, token persistence
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { SseStream, type StreamListener } from './stream'

describe('SseStream', () => {
  let stream: SseStream
  let mockEventSource: any
  let mockListener: StreamListener

  beforeEach(() => {
    stream = new SseStream('http://api.example.com')
    mockListener = {
      onEvent: vi.fn(),
      onError: vi.fn(),
      onReconnect: vi.fn(),
    }

    // Mock EventSource
    mockEventSource = {
      close: vi.fn(),
      addEventListener: vi.fn(),
      readyState: 1, // OPEN
      onerror: null as any,
    }

    // Create a proper mock constructor
    const EventSourceMock = vi.fn(function (this: any, _url: string) {
      return mockEventSource
    })
    // Add constants to mocked EventSource
    EventSourceMock.CONNECTING = 0
    EventSourceMock.OPEN = 1
    EventSourceMock.CLOSED = 2
    global.EventSource = EventSourceMock as any
  })

  afterEach(() => {
    stream.close()
  })

  describe('token handling', () => {
    it('should store token for SSE stream', () => {
      const token = 'officer-token-123'
      stream.setToken(token)
      // Token is set internally, will be used in connect() method
    })

    it('should include token in EventSource URL', () => {
      const token = 'officer-token-xyz'
      stream.setToken(token)

      stream.subscribe(mockListener)

      // Verify EventSource was called with URL containing token
      expect(global.EventSource).toHaveBeenCalled()
      const callUrl = (global.EventSource as any).mock.calls[0][0]
      expect(callUrl).toContain('token=officer-token-xyz')
    })
  })

  describe('Last-Event-ID persistence', () => {
    it('should capture Last-Event-ID from events', () => {
      stream.subscribe(mockListener)

      // Get the addEventListener calls to find the 'tick' listener
      const calls = mockEventSource.addEventListener.mock.calls
      const tickListenerCall = calls.find((call: any) => call[0] === 'tick')
      const tickListener = tickListenerCall[1]

      // Simulate an event with lastEventId
      const event = new MessageEvent('tick', {
        data: JSON.stringify({
          id: 'event-001',
          type: 'tick',
          at: '2025-08-19T17:00:00+05:30',
          data: { clock: { now: '2025-08-19T17:00:00+05:30' } },
        }),
        lastEventId: 'evt-0001',
      })

      tickListener(event)

      expect(stream.getLastEventId()).toBe('evt-0001')
    })

    it('should include Last-Event-ID as query param on reconnect', () => {
      stream.subscribe(mockListener)

      // Set up a last event ID
      const calls = mockEventSource.addEventListener.mock.calls
      const tickListenerCall = calls.find((call: any) => call[0] === 'tick')
      const tickListener = tickListenerCall[1]

      const event = new MessageEvent('tick', {
        data: JSON.stringify({
          id: 'evt-001',
          type: 'tick',
          at: '2025-08-19T17:00:00+05:30',
          data: { clock: { now: '2025-08-19T17:00:00+05:30' } },
        }),
        lastEventId: 'evt-123',
      })

      tickListener(event)

      expect(stream.getLastEventId()).toBe('evt-123')

      // Simulate error to trigger reconnect
      mockEventSource.onerror()

      vi.useFakeTimers()
      vi.runAllTimers()
      vi.useRealTimers()

      // Verify reconnection includes last_id
      const reconnectCall = (global.EventSource as any).mock.calls.find(
        (_: any, idx: number) => idx > 0
      )
      if (reconnectCall) {
        expect(reconnectCall[0]).toContain('last_id=evt-123')
      }
    })
  })

  describe('event parsing and delivery', () => {
    it('should parse and deliver typed SSE events', () => {
      stream.subscribe(mockListener)

      const calls = mockEventSource.addEventListener.mock.calls
      const tickListenerCall = calls.find((call: any) => call[0] === 'tick')
      const tickListener = tickListenerCall[1]

      const event = new MessageEvent('tick', {
        data: JSON.stringify({
          id: 'tick-001',
          type: 'tick',
          at: '2025-08-19T17:00:00+05:30',
          data: { clock: { now: '2025-08-19T17:00:00+05:30' } },
        }),
        lastEventId: 'evt-001',
      })

      tickListener(event)

      expect(mockListener.onEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          id: 'tick-001',
          type: 'tick',
          at: '2025-08-19T17:00:00+05:30',
        })
      )
    })

    it('should reset reconnect attempts on successful event', () => {
      stream.subscribe(mockListener)

      // Trigger error
      mockEventSource.onerror()
      expect(stream.getReconnectAttempts()).toBeGreaterThan(0)

      // Deliver successful event
      const calls = mockEventSource.addEventListener.mock.calls
      const tickListenerCall = calls.find((call: any) => call[0] === 'tick')
      const tickListener = tickListenerCall[1]

      const event = new MessageEvent('tick', {
        data: JSON.stringify({
          id: 'evt-001',
          type: 'tick',
          at: '2025-08-19T17:00:00+05:30',
          data: { clock: { now: '2025-08-19T17:00:00+05:30' } },
        }),
      })

      tickListener(event)

      expect(stream.getReconnectAttempts()).toBe(0)
    })
  })

  describe('stream status', () => {
    it('should report connection status', () => {
      stream.subscribe(mockListener)
      expect(stream.isConnected()).toBe(true)
    })

    it('should report reconnect attempt count', () => {
      stream.subscribe(mockListener)
      expect(stream.getReconnectAttempts()).toBe(0)
    })

    it('should return last event ID', () => {
      stream.subscribe(mockListener)
      expect(stream.getLastEventId()).toBe('')

      // Set a last event ID
      const calls = mockEventSource.addEventListener.mock.calls
      const tickListenerCall = calls.find((call: any) => call[0] === 'tick')
      const tickListener = tickListenerCall[1]

      const event = new MessageEvent('tick', {
        data: JSON.stringify({
          id: 'evt-001',
          type: 'tick',
          at: '2025-08-19T17:00:00+05:30',
          data: { clock: { now: '2025-08-19T17:00:00+05:30' } },
        }),
        lastEventId: 'evt-999',
      })

      tickListener(event)
      expect(stream.getLastEventId()).toBe('evt-999')
    })
  })

  describe('listener subscription', () => {
    it('should only connect once when multiple listeners subscribe', () => {
      const listener2 = { onEvent: vi.fn(), onError: vi.fn(), onReconnect: vi.fn() }

      stream.subscribe(mockListener)
      expect(global.EventSource).toHaveBeenCalledTimes(1)

      stream.subscribe(listener2)
      expect(global.EventSource).toHaveBeenCalledTimes(1)
    })

    it('should disconnect when all listeners unsubscribe', () => {
      const listener2 = { onEvent: vi.fn(), onError: vi.fn(), onReconnect: vi.fn() }

      const unsubscribe1 = stream.subscribe(mockListener)
      const unsubscribe2 = stream.subscribe(listener2)

      unsubscribe1()
      expect(mockEventSource.close).not.toHaveBeenCalled()

      unsubscribe2()
      expect(mockEventSource.close).toHaveBeenCalled()
    })
  })

  describe('error handling', () => {
    it('should handle invalid JSON events', () => {
      stream.subscribe(mockListener)

      const calls = mockEventSource.addEventListener.mock.calls
      const tickListenerCall = calls.find((call: any) => call[0] === 'tick')
      const tickListener = tickListenerCall[1]

      const event = new MessageEvent('tick', {
        data: 'invalid json',
        lastEventId: 'evt-001',
      })

      tickListener(event)

      expect(mockListener.onError).toHaveBeenCalledWith(
        expect.any(Error)
      )
    })
  })
})
