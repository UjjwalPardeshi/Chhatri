/**
 * Incremental `text/event-stream` parser (WHATWG SSE framing) used by the fetch-based stream
 * (SPEC §19.1). Handles CRLF/LF, multi-line `data:`, comments (keep-alive pings) and `id:`.
 */

export type RawSseMessage = { event: string; id: string | null; data: string }

const DEFAULT_EVENT = 'message'

export class SseParser {
  private buffer = ''
  private event = ''
  private data: string[] = []
  private id: string | null = null

  /** Feeds a decoded chunk; returns every message completed by it (in order). */
  push(chunk: string): RawSseMessage[] {
    this.buffer += chunk
    const out: RawSseMessage[] = []
    let newline = this.nextLineBreak()
    while (newline !== -1) {
      const line = this.buffer.slice(0, newline).replace(/\r$/, '')
      this.buffer = this.buffer.slice(newline + 1)
      const message = this.consumeLine(line)
      if (message) out.push(message)
      newline = this.nextLineBreak()
    }
    return out
  }

  private nextLineBreak(): number {
    return this.buffer.indexOf('\n')
  }

  private consumeLine(line: string): RawSseMessage | null {
    if (line === '') return this.dispatch()
    if (line.startsWith(':')) return null
    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    const rawValue = colon === -1 ? '' : line.slice(colon + 1)
    const value = rawValue.startsWith(' ') ? rawValue.slice(1) : rawValue
    if (field === 'event') this.event = value
    else if (field === 'data') this.data.push(value)
    else if (field === 'id' && !value.includes('\0')) this.id = value
    return null
  }

  private dispatch(): RawSseMessage | null {
    if (this.data.length === 0) {
      this.event = ''
      return null
    }
    const message = { event: this.event || DEFAULT_EVENT, id: this.id, data: this.data.join('\n') }
    this.event = ''
    this.data = []
    return message
  }
}
