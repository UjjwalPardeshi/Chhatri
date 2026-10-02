/**
 * Plain words for the H26 label (fs-05 section 10.1, fs-08 section 14): the reasons a component is not LIVE, and the
 * one line that says who answered. The mode, provider, model and reason all come from the API; nothing here decides them.
 */

export type LabelMode = 'LIVE' | 'SIMULATED' | 'FALLBACK'

const REASON_WORDS: Readonly<Record<string, string>> = Object.freeze({
  NO_KEY: 'no key set, already simulated',
  MODEL_NOT_SET: 'key set, model not set',
  MOCK_BACKEND: 'static demo: recorded sample',
  FREE_TIER_BLOCKED: 'free tier not allowed for this data',
  FORCED: 'forced for the demo',
  TIMEOUT: 'the provider timed out',
  RATE_LIMITED: 'the provider rate-limited the call',
  PROVIDER_ERROR: 'the provider returned an error',
  INVALID_REPLY: 'the reply was not usable',
  GUARD_BLOCKED: 'the answer guard blocked the reply',
  INJECTION_SUSPECTED: 'the message looked like an injection attempt',
})

/** The reason in words; an unknown code is shown as it came (never hidden). */
export function reasonWords(reason: string | null | undefined): string | null {
  if (!reason) return null
  return REASON_WORDS[reason] ?? reason
}

export type LabelFields = { mode?: LabelMode; provider?: string | null; model?: string | null; fallback_reason?: string | null }

/** "gemini · gemini-x" or just "template": the provider and model, when there are any. */
export function providerLine(label: LabelFields): string {
  return [label.provider, label.model].filter((part): part is string => Boolean(part)).join(' · ')
}

/** The details a "details" tap shows: provider and model, then the reason in words when it is not LIVE. */
export function detailsText(label: LabelFields): string {
  const reason = label.mode === 'LIVE' ? null : reasonWords(label.fallback_reason)
  return [providerLine(label), reason].filter((part) => part).join(' · ')
}
