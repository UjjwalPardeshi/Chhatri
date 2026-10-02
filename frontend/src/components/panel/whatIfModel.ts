/**
 * The words and the draft of the H24 what-if drawer (fs-08 11.1), as pure functions. The drawer changes the rule's
 * inputs, never the rule: every verdict, window and amount comes from the server's answer, and the only arithmetic
 * here is choosing which value a control shows (the judge's draft, else what happened).
 */
import type { WhatIfArea, WhatIfExample, WhatIfOverrides, WhatIfSide } from '../../api/opsWhatIf'
import { formatInr } from '../../lib/money'

export const SLIDER_MAX_PCT = 150
export const WHATIF_DEBOUNCE_MS = 150

export const ALERT_CHOICES = [
  { value: 'NONE', label: 'None' },
  { value: 'RAIN', label: 'Rain' },
  { value: 'CIVIC', label: 'Civic' },
  { value: 'HEATWAVE', label: 'Heat' },
] as const

export const isUntouched = (draft: WhatIfOverrides): boolean => Object.keys(draft).length === 0

/** The hours a control shows: the draft's, else what happened (an hour with nothing expected shows 0). */
export function shownHours(draft: WhatIfOverrides, baseline: WhatIfSide | null): number[] {
  return draft.hourly_index_pct ?? baseline?.hourly_index_pct.map((h) => h ?? 0) ?? []
}

/** A new draft with hour `index` set. The other hours keep what is shown now, so the request always sends all three. */
export function withHour(draft: WhatIfOverrides, baseline: WhatIfSide | null, index: number, value: number): WhatIfOverrides {
  return { ...draft, hourly_index_pct: shownHours(draft, baseline).map((h, i) => (i === index ? value : h)) }
}

export function resultLine(side: WhatIfSide, past: boolean): string {
  if (!side.fires) return past ? 'Did not fire' : 'Would not fire'
  const drop = side.drop_pct === undefined ? '' : `, ${side.drop_pct}% drop`
  return past ? `Fired: yes${drop}` : `Would fire: yes${drop}`
}

/** "Anil would be paid ₹1,205 (½ × ₹4,380 × 55%)": the owner's first name is the shop name before "'s". */
export function exampleLine(example: WhatIfExample): string {
  const who = example.shop_name.split("'s ")[0]
  const sum = example.formula_en.split(' = ')[0]
  const cap = example.capped ? `, capped at ${formatInr(example.cap_paise)}` : ''
  return `${who} would be paid ${example.amount_label} (${sum}${cap})`
}

export function rulesLine(fixed: WhatIfArea['fixed']): string {
  return `Rule: every hour below ${fixed.index_floor_pct}% for ${fixed.consecutive_hours} hours, at least ${fixed.min_shops_in_index} shops, window below the zone's bound of ${fixed.lower_bound_pct}%. Fixed here, not editable.`
}

export function evaluatedLine(answer: Pick<WhatIfArea, 'at' | 'window'>, clock: (iso: string) => string): string {
  return `Evaluated at ${clock(answer.at)}, window ${clock(answer.window.start)} to ${clock(answer.window.end)}`
}
