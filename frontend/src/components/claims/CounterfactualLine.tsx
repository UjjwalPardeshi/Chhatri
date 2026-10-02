/** H14: one line under the decision block, the top counterfactual the engine verified by re-running itself (fs-08 8.3). No model writes it. */
import type { Counterfactual } from '../../api/types'
import { COUNTERFACTUAL_NOTE } from './receiptParts'

export function CounterfactualLine({ counterfactuals }: { counterfactuals: readonly Counterfactual[] }) {
  const top = counterfactuals[0]
  if (!top) return null
  return (
    <p className="counterfactual">
      <span className="counterfactual__text">{top.text_en}</span>
      <span className="counterfactual__note muted">{COUNTERFACTUAL_NOTE}</span>
    </p>
  )
}
