/**
 * SSE Stream Handler - EventSource with auto-reconnect
 * Handles server-sent events with Last-Event-ID for resumption
 */

import type { SseEvent } from './types'

export interface StreamListener {
  onEvent: (event: SseEvent) => void
  onError: (error: Error) => void
  onReconnect: () => void
}

export class SseStream {
  private eventSource: EventSource | null = null
  private baseUrl: string
  private token: string | null = null
  private lastEventId: string = ''
  private reconnectAttempts: number = 0
  private maxReconnectAttempts: number = 10
  private reconnectDelay: number = 1000 // ms
  private listeners: Set<StreamListener> = new Set()

  constructor(baseUrl: string = import.meta.env.VITE_API_BASE || '') {
    this.baseUrl = baseUrl
  }

  /**
   * Set authentication token for SSE stream
   * Token is appended as URL query parameter since EventSource doesn't support Authorization headers
   * (SPEC §19, token is persisted across reconnects via Last-Event-ID)
   */
  setToken(token: string): void {
    this.token = token
    // Reconnect if already connected to apply new token
    if (this.isConnected()) {
      this.disconnect()
      this.connect()
    }
  }

  subscribe(listener: StreamListener): () => void {
    this.listeners.add(listener)
    if (this.listeners.size === 1) {
      this.connect()
    }

    return () => {
      this.listeners.delete(listener)
      if (this.listeners.size === 0) {
        this.disconnect()
      }
    }
  }

  private connect(): void {
    if (this.eventSource) {
      return
    }

    const url = new URL(`${this.baseUrl}/api/stream`)

    // Append token as query parameter (EventSource doesn't support Authorization headers)
    if (this.token) {
      url.searchParams.set('token', this.token)
    }

    if (this.lastEventId) {
      // Send Last-Event-ID as query param for resumption
      url.searchParams.set('last_id', this.lastEventId)
    }

    this.eventSource = new EventSource(url.toString())

    // Set up event handlers for each event type
    this.setupEventListener('scenario')
    this.setupEventListener('tick')
    this.setupEventListener('zone')
    this.setupEventListener('hexes')
    this.setupEventListener('alert')
    this.setupEventListener('trigger')
    this.setupEventListener('decision')
    this.setupEventListener('payout')
    this.setupEventListener('instalment')
    this.setupEventListener('message')
    this.setupEventListener('soundbox')
    this.setupEventListener('case')
    this.setupEventListener('audit')
    this.setupEventListener('kpis')

    this.eventSource.onerror = () => {
      this.handleConnectionError()
    }
  }

  private setupEventListener(eventType: string): void {
    if (!this.eventSource) return

    this.eventSource.addEventListener(eventType, (e: Event) => {
      if (!(e instanceof MessageEvent)) return

      try {
        this.lastEventId = e.lastEventId || this.lastEventId
        const data = JSON.parse(e.data) as SseEvent

        this.reconnectAttempts = 0

        this.listeners.forEach((listener) => {
          try {
            listener.onEvent(data)
          } catch (error) {
            console.error('Listener error:', error)
          }
        })
      } catch (error) {
        const err = error instanceof Error ? error : new Error(String(error))
        this.listeners.forEach((listener) => {
          listener.onError(err)
        })
      }
    })
  }

  private handleConnectionError(): void {
    this.disconnect()

    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), 30000)

      this.listeners.forEach((listener) => {
        listener.onReconnect()
      })

      setTimeout(() => {
        this.connect()
      }, delay)
    } else {
      const error = new Error(
        'Max reconnection attempts reached'
      )
      this.listeners.forEach((listener) => {
        listener.onError(error)
      })
    }
  }

  private disconnect(): void {
    if (this.eventSource) {
      this.eventSource.close()
      this.eventSource = null
    }
  }

  public close(): void {
    this.listeners.clear()
    this.disconnect()
  }

  public getLastEventId(): string {
    return this.lastEventId
  }

  public isConnected(): boolean {
    return (
      this.eventSource !== null &&
      this.eventSource.readyState === 1 // EventSource.OPEN
    )
  }

  public getReconnectAttempts(): number {
    return this.reconnectAttempts
  }
}

const sseStream = new SseStream()
export { sseStream }
