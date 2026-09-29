/**
 * Money formatting utilities
 * Identical to backend chhatri.money module (SPEC §4.2)
 */

/**
 * Format integer paise to Indian rupee display format
 * Examples:
 * - 138000 paise → "₹1,380"
 * - 15890000 paise → "₹1,58,900"
 * - 180 paise → "₹1.80"
 * - 138 paise → "₹1.38"
 */
export function formatInr(paise: number): string {
  if (!Number.isInteger(paise) || paise < 0) {
    throw new Error(`Invalid paise amount: ${paise}`)
  }

  // Convert paise to rupees
  const rupees = paise / 100
  const wholePart = Math.floor(rupees)
  const fractionalPart = Math.round((rupees - wholePart) * 100)

  // Format with Indian digit grouping
  const formatted = formatIndianNumber(wholePart)

  // Add fractional part if non-zero
  if (fractionalPart > 0) {
    return `₹${formatted}.${String(fractionalPart).padStart(2, '0')}`
  }

  return `₹${formatted}`
}

/**
 * Format a number with Indian digit grouping (XX,XX,XXX)
 */
function formatIndianNumber(num: number): string {
  const str = String(num)
  const len = str.length

  if (len <= 3) {
    return str
  }

  // Split into groups: last 3 digits, then groups of 2 from right to left
  const lastThree = str.slice(-3)
  const remaining = str.slice(0, -3)

  // Group remaining digits in pairs from right to left
  const groups: string[] = []
  let current = remaining

  while (current.length > 2) {
    groups.unshift(current.slice(-2))
    current = current.slice(0, -2)
  }

  if (current.length > 0) {
    groups.unshift(current)
  }

  groups.push(lastThree)
  return groups.join(',')
}

/**
 * Color scale for hex visualization
 * Red at 40%, amber at 70%, green at 100%+
 * Follows deck's color scheme
 */
export function getHexColor(
  indexPct: number | null,
  options: { lighter?: boolean } = {}
): string {
  if (indexPct === null || indexPct === undefined) {
    return '#e5e7eb' // neutral gray for no data
  }

  // Clamp to 0-100+ range
  const value = Math.max(0, indexPct)

  if (value < 40) {
    // Deep red zone (0-40%)
    return options.lighter ? '#fca5a5' : '#dc2626'
  }

  if (value < 70) {
    // Red to amber gradient (40-70%)
    const ratio = (value - 40) / 30
    // Interpolate between red (#dc2626) and amber (#e39a4f)
    return interpolateColor('#dc2626', '#e39a4f', ratio)
  }

  if (value < 100) {
    // Amber to green gradient (70-100%)
    const ratio = (value - 70) / 30
    // Interpolate between amber (#e39a4f) and green (#15803d)
    return interpolateColor('#e39a4f', '#15803d', ratio)
  }

  // Green for 100%+
  return options.lighter ? '#86efac' : '#15803d'
}

/**
 * Interpolate between two hex colors
 */
function interpolateColor(color1: string, color2: string, ratio: number): string {
  const c1 = parseInt(color1.slice(1), 16)
  const c2 = parseInt(color2.slice(1), 16)

  const r1 = (c1 >> 16) & 255
  const g1 = (c1 >> 8) & 255
  const b1 = c1 & 255

  const r2 = (c2 >> 16) & 255
  const g2 = (c2 >> 8) & 255
  const b2 = c2 & 255

  const r = Math.round(r1 + (r2 - r1) * ratio)
  const g = Math.round(g1 + (g2 - g1) * ratio)
  const b = Math.round(b1 + (b2 - b1) * ratio)

  // Use unsigned right shift to ensure 32-bit unsigned integer
  const result = ((r & 255) << 16) | ((g & 255) << 8) | (b & 255)
  return '#' + result.toString(16).padStart(6, '0')
}

/**
 * Parse INR string back to paise
 * Inverse of formatInr
 */
export function parseInr(formatted: string): number {
  // Remove ₹ and spaces, then parse
  const cleaned = formatted.replace(/[₹\s,]/g, '')
  const rupees = parseFloat(cleaned)

  if (!Number.isFinite(rupees)) {
    throw new Error(`Invalid INR format: ${formatted}`)
  }

  return Math.round(rupees * 100)
}
