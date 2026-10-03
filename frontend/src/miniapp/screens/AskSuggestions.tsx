/**
 * The empty state of the Ask screen (screens 5.1): what can be asked, the rule that the rules decide every payout, and
 * up to four ready questions that apply to this merchant. Tapping one sends its text. While the claims call decides
 * which apply, the chips are skeletons.
 */
import { ChevronRight } from 'lucide-react'

import { ta, type AskCopyKey } from '../copy/ask'
import type { Lang } from '../lib/lang'
import { Skeleton } from '../ui/skeleton'

export const MAX_SUGGESTIONS = 4

export type SuggestionFacts = { hasDecision: boolean; hasPaidDecision: boolean; hasLoan: boolean }

const ORDER = [
  ['ask.suggest.why', (f: SuggestionFacts) => f.hasDecision],
  ['ask.suggest.bigger', (f: SuggestionFacts) => f.hasPaidDecision],
  ['ask.suggest.covered', () => true],
  ['ask.suggest.starts', () => true],
  ['ask.suggest.waiting', () => true],
  ['ask.suggest.question', () => true],
  ['ask.suggest.instalment', (f: SuggestionFacts) => f.hasLoan],
] as const satisfies readonly (readonly [AskCopyKey, (facts: SuggestionFacts) => boolean])[]

/** The first four that apply, in the order of the design. */
export function suggestionKeys(facts: SuggestionFacts): AskCopyKey[] {
  return ORDER.filter(([, applies]) => applies(facts)).map(([key]) => key).slice(0, MAX_SUGGESTIONS)
}

type Props = { lang: Lang; facts: SuggestionFacts | null; disabled: boolean; onPick: (text: string) => void }

export function AskSuggestions({ lang, facts, disabled, onPick }: Props) {
  return (
    <div data-testid="ask-empty" className="flex flex-col gap-3">
      <p className="text-md font-bold">{ta('ask.scope', lang)}</p>
      <p className="text-sm text-ink-2">{ta('ask.rules_decide', lang)}</p>
      <p className="pt-2 text-caption font-bold text-ink-2">{ta('ask.suggest.title', lang)}</p>
      {facts === null ? (
        <div data-testid="ask-suggest-loading" className="flex flex-col gap-2">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-12 w-full rounded-lg" />
          ))}
        </div>
      ) : (
        <ul className="flex flex-col overflow-hidden rounded-lg border bg-card [&>*+*]:border-t [&>*+*]:border-line-soft">
          {suggestionKeys(facts).map((key) => (
            <li key={key}>
              <button
                type="button"
                data-testid="ask-suggest"
                data-key={key}
                disabled={disabled}
                className="flex min-h-12 w-full items-center justify-between gap-3 px-4 py-3 text-left text-md font-medium outline-none hover:bg-paper-2 focus-visible:ring-[3px] focus-visible:ring-inset focus-visible:ring-ring/50 disabled:opacity-50"
                onClick={() => onPick(ta(key, lang))}
              >
                {ta(key, lang)}
                <ChevronRight className="size-5 shrink-0 text-faint" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
