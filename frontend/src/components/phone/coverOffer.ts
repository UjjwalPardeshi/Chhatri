/**
 * The BLOCKED live test in structured form (SPEC §13.4 COVER_BLOCKED and COVER_LINK, §13.6):
 * "New cover starts after the waiting period — from {starts_on_en}. …" and "To buy cover for
 * later, pay {first_payment} ({per_day}/day) here: {url}". Both lines are fixed catalogue
 * templates, so the merchant page can show a BLOCKED badge with the start date and draw the Paytm
 * link as a payment card without any extra API field.
 */
import type { Message } from '../../api/types'

const BLOCKED = /^New cover starts after the waiting period — from (.+?)\. /
const LINK = /^To buy cover for later, pay (₹[\d,]+(?:\.\d{2})?) \((₹[\d,]+(?:\.\d{2})?)\/day\) here: (https:\/\/\S+)$/

export type CoverLink = { firstPayment: string; perDay: string; url: string }
export type CoverOffer = { startsOn: string | null; link: CoverLink | null }

/** The Paytm premium link in a COVER_LINK message, or null for any other message. */
export function coverLink(message: Pick<Message, 'direction' | 'text_en'>): CoverLink | null {
  if (message.direction !== 'OUTBOUND' || !message.text_en) return null
  const match = LINK.exec(message.text_en)
  return match ? { firstPayment: match[1], perDay: match[2], url: match[3] } : null
}

/** The latest blocked cover request in a conversation (null when cover was never refused). */
export function coverOffer(messages: readonly Pick<Message, 'direction' | 'text_en'>[]): CoverOffer | null {
  const outbound = messages.filter((m) => m.direction === 'OUTBOUND' && m.text_en)
  const blocked = outbound.findLast((m) => BLOCKED.test(m.text_en ?? ''))
  if (!blocked) return null
  const startsOn = BLOCKED.exec(blocked.text_en ?? '')?.[1] ?? null
  const link = outbound.map((m) => coverLink(m)).findLast((l) => l !== null) ?? null
  return { startsOn, link }
}
