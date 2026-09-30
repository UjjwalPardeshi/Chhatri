import { describe, expect, it } from 'vitest'

import { SseParser } from './sse'

describe('SseParser (text/event-stream framing)', () => {
  it('parses events split across chunks', () => {
    const parser = new SseParser()
    expect(parser.push('id: 7\nevent: tick\nda')).toEqual([])
    expect(parser.push('ta: {"a":1}\n\n')).toEqual([{ event: 'tick', id: '7', data: '{"a":1}' }])
  })

  it('handles CRLF, multi-line data, comments and default event names', () => {
    const parser = new SseParser()
    const out = parser.push(': ping\r\n\r\ndata: line1\r\ndata:line2\r\n\r\n')
    expect(out).toEqual([{ event: 'message', id: null, data: 'line1\nline2' }])
  })

  it('keeps the last id across events and ignores ids with NUL', () => {
    const parser = new SseParser()
    parser.push('id: 3\nevent: a\ndata: x\n\n')
    expect(parser.push('event: b\ndata: y\n\n')).toEqual([{ event: 'b', id: '3', data: 'y' }])
    expect(parser.push('id: bad\0\ndata: z\n\n')[0].id).toBe('3')
  })

  it('drops an event with no data and ignores unknown fields', () => {
    const parser = new SseParser()
    expect(parser.push('event: tick\nretry: 10\n\n')).toEqual([])
    expect(parser.push('field\ndata\n\n')).toEqual([{ event: 'message', id: null, data: '' }])
  })
})
