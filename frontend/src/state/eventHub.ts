/** Tiny typed pub/sub so pages can react to live SSE events (SPEC §19.1) without prop drilling. */
import type { SseEvent, SseEventType } from '../api/types'

export type EventHandler = (event: SseEvent) => void

export class EventHub {
  private handlers = new Map<SseEventType | '*', Set<EventHandler>>()

  on(types: readonly (SseEventType | '*')[], handler: EventHandler): () => void {
    for (const type of types) {
      const set = this.handlers.get(type) ?? new Set<EventHandler>()
      set.add(handler)
      this.handlers.set(type, set)
    }
    return () => {
      for (const type of types) this.handlers.get(type)?.delete(handler)
    }
  }

  emit(event: SseEvent): void {
    const targets = [...(this.handlers.get(event.type) ?? []), ...(this.handlers.get('*') ?? [])]
    for (const handler of targets) {
      try {
        handler(event)
      } catch (error) {
        console.error(`[events] handler for ${event.type} failed`, error)
      }
    }
  }
}
