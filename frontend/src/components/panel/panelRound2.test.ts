/** Live panel wording (SPEC §19.2 FeedItem parts, B3 live window, §20 stream status). */
import { describe, expect, it } from 'vitest'

import { streamMark } from './EventFeed'
import { partText } from './feedGroups'
import { liveNow } from './zoneTrend'

describe('feed parts', () => {
  it('reads each group’s figure in its own words', () => {
    expect(partText('instalment', { zone: 'Z3', figure: '56' })).toBe('56 in Z3')
    expect(partText('watch', { zone: 'Z3', figure: '2 h' })).toBe('Z3 for 2 h')
    expect(partText('trigger', { zone: 'Z3', figure: '38%' })).toBe('Z3 at 38%')
    expect(partText('payout', { zone: 'Z3', figure: '₹1,79,820' })).toBe('Z3 ₹1,79,820')
    expect(partText('payout', { zone: 'Z3', figure: null })).toBe('Z3')
  })

  it('marks the stream as streaming or reconnecting', () => {
    expect(streamMark('open')).toEqual({ text: 'streaming', tone: 'live' })
    expect(streamMark('reconnecting')).toEqual({ text: 'reconnecting', tone: 'down' })
  })
})

describe('live now', () => {
  it('shows the live window only when it differs from the completed-hours index', () => {
    expect(liveNow({ status: 'watch', live_index_pct: 42 }, { pct: 45 })).toBe(42)
    expect(liveNow({ status: 'watch', live_index_pct: 45 }, { pct: 45 })).toBeNull()
    expect(liveNow({ status: 'triggered', live_index_pct: 30 }, { pct: 37 })).toBeNull()
    expect(liveNow({ status: 'watch', live_index_pct: null }, { pct: 45 })).toBeNull()
  })
})
