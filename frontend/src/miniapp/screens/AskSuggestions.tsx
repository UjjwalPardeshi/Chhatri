/**
 * The empty state of the Ask screen (screens 5.1): what can be asked, the rule that the rules decide every payout, and
 * up to four ready questions that apply to this merchant. Tapping one sends its text. While the claims call decides
 * which apply, the chips are skeletons.
 */
import { ta, type AskCopyKey } from '../copy/ask'
import type { Lang } from '../lib/lang'
import { Button } from '../ui/button'
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
      <p className="text-md font-medium">{ta('ask.scope', lang)}</p>
      <p className="text-sm text-ink-2">{ta('ask.rules_decide', lang)}</p>
      <p className="pt-2 text-sm font-medium text-ink-3">{ta('ask.suggest.title', lang)}</p>
      {facts === null ? (
        <div data-testid="ask-suggest-loading" className="flex flex-wrap gap-2">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-11 w-44 rounded-full" />
          ))}
        </div>
      ) : (
        <ul className="flex flex-col items-start gap-2">
          {suggestionKeys(facts).map((key) => (
            <li key={key}>
              <Button data-testid="ask-suggest" data-key={key} variant="outline" disabled={disabled} className="h-auto min-h-11 whitespace-normal rounded-full py-2 text-left" onClick={() => onPick(ta(key, lang))}>
                {ta(key, lang)}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
