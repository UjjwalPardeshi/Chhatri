/**
 * The H26 mode word (design system 11): LIVE green, SIMULATED grey, FALLBACK orange, each with a glyph and the word,
 * so colour is never the only signal. Optional "details" tap shows provider, model and the reason in plain words.
 */
import { useState } from 'react'

import { detailsText, type LabelFields, type LabelMode } from '../../lib/providerLabels'

const GLYPH: Readonly<Record<LabelMode, string>> = { LIVE: '●', SIMULATED: '○', FALLBACK: '▲' }

export function ModeWord({ mode }: { mode: LabelMode }) {
  return (
    <span className={`mode-chip mode-chip--${mode.toLowerCase()}`} data-mode={mode}>
      <span aria-hidden="true">{GLYPH[mode]}</span> {mode}
    </span>
  )
}

/** Mode word plus a "details" button that opens one line (provider, model, reason). */
export function ModeChip({ label }: { label: LabelFields }) {
  const [open, setOpen] = useState(false)
  if (!label.mode) return null
  const details = detailsText(label)
  return (
    <span className="mode-chip-wrap">
      <ModeWord mode={label.mode} />
      {details ? (
        <button type="button" className="mode-chip__details" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
          details
        </button>
      ) : null}
      {open && details ? <span className="mode-chip__line">{details}</span> : null}
    </span>
  )
}
