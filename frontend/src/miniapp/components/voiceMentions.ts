/**
 * The rules of the confirmation chips (H18, fs-05 section 11.4), apart from the screen. A chip is confirmed by what it
 * says, not by its number, so editing the words around an amount keeps its confirmation while a new amount or date
 * starts unconfirmed. A mention with no value (words the parser could not read) can never be confirmed: the merchant
 * types the number and the text is read again. The word कल is a date with two meanings, so it is confirmed only with
 * the choice of yesterday or tomorrow.
 */
import type { Mention } from '../api/ask'

export type KalChoice = 'yesterday' | 'tomorrow'

const KAL_WORDS: ReadonlySet<string> = new Set(['कल', 'kal'])

/** True for the Hindi "कल": a date with no value, whose chip asks which day was meant. */
export function isKal(mention: Mention): boolean {
  return mention.kind === 'date' && mention.value === null && KAL_WORDS.has(mention.heard.toLowerCase())
}

/** True when the parser found words it cannot turn into a value: the chip says "please type the number". */
export function needsTyping(mention: Mention): boolean {
  return mention.value === null && !isKal(mention)
}

export function mentionKey(mention: Mention, choice?: KalChoice): string {
  if (isKal(mention)) return `kal|${choice ?? ''}`
  return `${mention.kind}|${mention.value ?? mention.heard}`
}

export function isConfirmed(mention: Mention, confirmed: ReadonlySet<string>): boolean {
  if (needsTyping(mention)) return false
  if (isKal(mention)) return confirmed.has('kal|yesterday') || confirmed.has('kal|tomorrow')
  return confirmed.has(mentionKey(mention))
}

/** The chips not yet confirmed. `confirmed` holds keys. */
export const pendingMentions = (mentions: readonly Mention[], confirmed: ReadonlySet<string>): Mention[] => mentions.filter((m) => !isConfirmed(m, confirmed))

/** The ids the server wants in `confirmed_mentions`: the chips whose key is confirmed. */
export function confirmedIds(mentions: readonly Mention[], confirmed: ReadonlySet<string>): string[] {
  return mentions.filter((m) => isConfirmed(m, confirmed)).map((m) => m.id)
}

/** Send works when every chip is confirmed. A text with no amount or date has no chip, so it works at once. */
export const allConfirmed = (mentions: readonly Mention[], confirmed: ReadonlySet<string>): boolean => pendingMentions(mentions, confirmed).length === 0
