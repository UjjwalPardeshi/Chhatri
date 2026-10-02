/** A row of jargon terms ("Words to know"): each a `JargonTerm` button, wrapping onto more lines instead of scrolling sideways. */
import type { TermId } from '../glossary'
import { JargonTerm } from './JargonTerm'

export function JargonTerms({ ids, testId }: { ids: readonly TermId[]; testId?: string }) {
  if (ids.length === 0) return null
  return (
    <ul data-testid={testId} className="flex flex-wrap gap-x-3 gap-y-0">
      {ids.map((id) => (
        <li key={id}>
          <JargonTerm id={id} />
        </li>
      ))}
    </ul>
  )
}
