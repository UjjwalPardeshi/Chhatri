/** X4: the lender's answer to this decision's holiday request, in plain words (fs-08 8.4, fs-03 section 8). */
import type { LenderReasonCode, ReceiptEdi } from '../../api/types'
import { weekdayDayLabel } from '../../lib/time'

/** Refusal reasons in words (fs-03 section 8.3). FLAG_OFF means the lender is not switched on. */
const REASON_WORDS: Readonly<Record<LenderReasonCode, string>> = Object.freeze({
  FLAG_OFF: 'the lender link is switched off',
  NOT_ACTIVE: 'the loan is not active',
  IN_ARREARS: 'the loan has an amount overdue',
  NO_ALLOWANCE: 'your holiday allowance is used up',
})

export function holidayWords(edi: ReceiptEdi): string {
  const due = weekdayDayLabel(edi.instalment_date)
  switch (edi.status) {
    case 'GRANTED':
      return `Lender granted the holiday: ${edi.instalment_label} due ${due}`
    case 'REFUSED': {
      const code = edi.reason_code
      return code ? `Lender refused the holiday (${code}): ${REASON_WORDS[code]}` : 'Lender refused the holiday'
    }
    case 'NO_RESPONSE':
      return `Lender did not answer: the ${edi.instalment_label} instalment stays due`
    default:
      return `Lender asked to pause the ${edi.instalment_label} instalment due ${due}`
  }
}

const TONES = { GRANTED: 'green', REFUSED: 'red', NO_RESPONSE: 'amber', REQUESTED: 'blue' } as const

export function HolidayRow({ edi }: { edi: ReceiptEdi | null | undefined }) {
  if (!edi) return null
  return (
    <p className="holiday-row" data-status={edi.status}>
      <span className="eyebrow">Loan instalment</span>
      <span className={`badge badge--${TONES[edi.status]}`}>{edi.status === 'NO_RESPONSE' ? 'NO ANSWER' : edi.status}</span>
      <span>{holidayWords(edi)}</span>
      <span className="muted num">
        {edi.request_id} · {edi.lender}
      </span>
    </p>
  )
}
