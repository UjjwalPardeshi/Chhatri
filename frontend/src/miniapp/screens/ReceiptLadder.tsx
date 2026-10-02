/**
 * "If you disagree" (fs-04 10.2, fs-06 5.4): the four steps in order, as the API lists them. Step 1 is our own claims
 * officer and carries its clock from the rules (`first_step_hours`, the dispute SLA); the others name who they are and
 * say the response time is to be confirmed with the insurer. A step the app has no name for is shown as the API sent it.
 */
import type { ReceiptGrievance } from '../../api/types'
import { langAttr } from '../components/StepperLine'
import { t, type CopyKey } from '../lib/copy'
import { useMiniapp } from '../shell/MiniappContext'

const STEP_KEYS: Readonly<Record<string, CopyKey>> = {
  PAYTM_DISPUTE: 'grv.step.PAYTM_DISPUTE',
  INSURER_GRO: 'grv.step.INSURER_GRO',
  BIMA_BHAROSA: 'grv.step.BIMA_BHAROSA',
  OMBUDSMAN: 'grv.step.OMBUDSMAN',
}

export function ReceiptLadder({ grievance }: { grievance: ReceiptGrievance }) {
  const { lang } = useMiniapp()
  return (
    <ol data-testid="receipt-grievance-path" className="flex flex-col gap-2">
      {grievance.ladder.map((step, index) => (
        <li key={step} data-step={step} className="flex items-start gap-3">
          <span aria-hidden="true" className="num flex size-6 shrink-0 items-center justify-center rounded-full bg-secondary text-xs font-medium text-ink-2">
            {index + 1}
          </span>
          <div className="flex min-w-0 flex-col">
            <p className="text-sm font-medium text-foreground">
              {Object.hasOwn(STEP_KEYS, step) ? t(STEP_KEYS[step], lang) : <span lang={langAttr('en', lang)}>{step}</span>}
            </p>
            <p className="text-caption text-ink-3">
              {index === 0 ? t('grv.clock.own', lang, { sla_hours: grievance.first_step_hours }) : t('grv.clock.confirm.insurer', lang)}
            </p>
          </div>
        </li>
      ))}
    </ol>
  )
}
