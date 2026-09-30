/**
 * Voice-note waveform (deck slides 1 and 7): 24 bars whose heights come from the message id, so
 * the same note always draws the same shape (SPEC §0.2 determinism, no randomness). While the note
 * plays, a second copy of the bars fills from the left over the note's duration. The compact form
 * (14 shorter bars) sits beside the play button of Chhatri's spoken text lines.
 */
import type { CSSProperties } from 'react'

export const WAVE_BARS = 24
/** Compact waveform: fewer, shorter bars (at least MIN_COMPACT_PX tall). */
export const COMPACT_BARS = 14
const COMPACT_SCALE = 0.7
const MIN_COMPACT_PX = 3
const MIN_BAR_PX = 4
const MAX_BAR_PX = 18
/** FNV-1a 32-bit constants. */
const FNV_OFFSET = 0x811c9dc5
const FNV_PRIME = 0x01000193
const UINT32 = 0x1_0000_0000

function fnv1a(text: string): number {
  let hash = FNV_OFFSET
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i)
    hash = Math.imul(hash, FNV_PRIME) >>> 0
  }
  return hash
}

/** Deterministic bar heights (px) for a seed: a speech-like envelope with per-bar variation. */
export function waveHeights(seed: string, bars: number = WAVE_BARS): number[] {
  let state = fnv1a(seed) || 1
  return Array.from({ length: bars }, (_, i) => {
    state ^= state << 13
    state ^= state >>> 17
    state ^= state << 5
    state >>>= 0
    const envelope = Math.sin((Math.PI * (i + 0.5)) / bars) ** 0.6
    const jitter = 0.35 + 0.65 * (state / UINT32)
    return Math.round(MIN_BAR_PX + (MAX_BAR_PX - MIN_BAR_PX) * envelope * jitter)
  })
}

type Props = { seed: string; seconds: number; playKey: number; compact?: boolean }

function Bars({ heights }: { heights: readonly number[] }) {
  return (
    <>
      {heights.map((h, i) => (
        <span key={i} style={{ height: `${h}px` }} />
      ))}
    </>
  )
}

export function Waveform({ seed, seconds, playKey, compact = false }: Props) {
  const heights = compact ? waveHeights(seed, COMPACT_BARS).map((h) => Math.max(MIN_COMPACT_PX, Math.round(h * COMPACT_SCALE))) : waveHeights(seed)
  const style = { '--voice-duration': `${Math.max(1, seconds)}s` } as CSSProperties
  return (
    <span className={compact ? 'wave wave--compact' : 'wave'} aria-hidden="true" style={style}>
      <span className="wave__bars">
        <Bars heights={heights} />
      </span>
      {playKey > 0 ? (
        <span key={playKey} className="wave__bars wave__bars--played">
          <Bars heights={heights} />
        </span>
      ) : null}
    </span>
  )
}
