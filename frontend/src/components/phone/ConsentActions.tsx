/**
 * The doctor question on the console phone (design 2.6 message shape 2): "May we ask Dr S. Rao at KEM Hospital, Parel
 * to confirm your visit?" with Yes and No, sent as CONSENT_YES or CONSENT_NO to the same confirm route as the slip
 * answer. Either way the claim is filed; No sends it to a person. Shown on the last message only, like the slip buttons.
 */
import type { Message, PrecheckAction } from '../../api/types'
import { AnswerLines, useAnswer } from './PrecheckActions'
import type { ConsentCard } from './precheckCard'

const CONSENT_ACTIONS: Readonly<Record<string, PrecheckAction>> = { CONSENT_YES: 'CONSENT_YES', CONSENT_NO: 'CONSENT_NO' }

export function ConsentActions({ message, card }: { message: Message; card: ConsentCard }) {
  const state = useAnswer(message.merchant_id, card.consent_for)
  const buttons = card.actions.filter((action) => Object.hasOwn(CONSENT_ACTIONS, action.kind))
  return (
    <fieldset className="precheck-actions" aria-label="May we ask the doctor?">
      {state.done
        ? null
        : buttons.map((action) => (
            <button
              key={action.kind}
              type="button"
              className={action.kind === 'CONSENT_YES' ? 'btn btn--primary' : 'btn'}
              disabled={state.busy}
              onClick={() => void state.answer(CONSENT_ACTIONS[action.kind])}
            >
              {action.label_hi ? `${action.label_hi} · ${action.label_en}` : action.label_en}
            </button>
          ))}
      <AnswerLines state={state} />
    </fieldset>
  )
}
