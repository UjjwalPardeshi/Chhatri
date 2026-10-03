/**
 * What the slip reader saw, on every pre-check card of the console phone (finding: "the phone never shows what was
 * read"): the six fields as plain text (a value, "not clear" or "not on the slip") and the three checklist lines in
 * Hindi and English. Never a confidence number or a percentage; nothing can be edited.
 */
import type { SlipSlotKey } from '../../api/types'
import { dayLabel } from '../../lib/time'
import type { PrecheckCard } from './precheckCard'

const FIELD_LABELS: Readonly<Record<SlipSlotKey, string>> = {
  patient_name: 'Patient',
  admission_date: 'Admitted',
  discharge_date: 'Discharged',
  hospital_name: 'Hospital',
  doctor_name: 'Doctor',
  doctor_registration_no: 'Registration no.',
}

const DATE_KEYS: readonly SlipSlotKey[] = ['admission_date', 'discharge_date']

function shown(key: SlipSlotKey, value: string | null, state: string): string {
  if (state === 'READ' && value) return DATE_KEYS.includes(key) ? dayLabel(value) : value
  return state === 'MISSING' ? 'not clear' : 'not on the slip'
}

export function PrecheckFields({ card }: { card: PrecheckCard }) {
  if (card.slots.length === 0 && card.checklist.length === 0) return null
  return (
    <div className="precheck-fields" data-testid="precheck-fields" data-status={card.status}>
      <dl className="precheck-fields__list">
        {card.slots.map((slot) => (
          <div key={slot.key} className="precheck-fields__row" data-state={slot.state} data-key={slot.key}>
            <dt>{FIELD_LABELS[slot.key]}</dt>
            <dd className={slot.state === 'READ' ? undefined : 'muted'}>{shown(slot.key, slot.value, slot.state)}</dd>
          </div>
        ))}
      </dl>
      {card.checklist.length > 0 ? (
        <ul className="precheck-fields__checks">
          {card.checklist.map((line) => (
            <li key={line.id} data-state={line.state}>
              <span aria-hidden="true">{line.state === 'PASS' ? '✓' : '!'}</span>{' '}
              {line.text_hi ? (
                <span className="hi" lang="hi">
                  {line.text_hi}
                </span>
              ) : null}
              {line.text_hi && line.text_en ? ' · ' : null}
              {line.text_en}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
