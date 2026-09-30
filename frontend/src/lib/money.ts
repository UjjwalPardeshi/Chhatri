/**
 * `formatInr` — the console mirror of `chhatri.money.format_inr` (SPEC §4.2): integer paise in,
 * `₹1,380` / `₹1,58,900` / `₹1.80` / `-₹50` out, Indian digit grouping, decimals only when the
 * amount is not whole rupees. Shared test vectors live in `money.vectors.json` (generated from the
 * backend implementation). The UI shows server `*_label` strings; this is for derived totals only.
 */

const PAISE_PER_RUPEE = 100

/** 1234567 → "12,34,567" (non-negative integers only), like `chhatri.money.indian_grouping`. */
export function indianGrouping(n: number): string {
  if (!Number.isSafeInteger(n) || n < 0) {
    throw new RangeError(`indianGrouping expects a non-negative integer, got ${n}`)
  }
  const digits = String(n)
  if (digits.length <= 3) return digits
  let head = digits.slice(0, -3)
  const tail = digits.slice(-3)
  const groups: string[] = []
  while (head.length > 2) {
    groups.unshift(head.slice(-2))
    head = head.slice(0, -2)
  }
  if (head) groups.unshift(head)
  return `${groups.join(',')},${tail}`
}

export function formatInr(paise: number): string {
  if (!Number.isSafeInteger(paise)) {
    throw new TypeError(`formatInr expects integer paise, got ${paise}`)
  }
  const sign = paise < 0 ? '-' : ''
  const abs = Math.abs(paise)
  const whole = Math.floor(abs / PAISE_PER_RUPEE)
  const frac = abs % PAISE_PER_RUPEE
  const text = `₹${indianGrouping(whole)}${frac ? `.${String(frac).padStart(2, '0')}` : ''}`
  return sign + text
}
