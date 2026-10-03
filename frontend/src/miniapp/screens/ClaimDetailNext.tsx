/**
 * "What happens next" on S5 once the payout is credited: the ordered steps of `nextSteps`, read from the decision's
 * receipt and the merchant's cover. The card asks for the receipt only for a paid claim and holds its place while the
 * receipt loads, so the steps below do not jump; it draws nothing when the receipt fails, because the steps below
 * already say what happened. The payout rail and the lender say SIMULATED here as they do on the steps.
 */
import { SimulatedLine } from '../components/Stepper'
import { LineText } from '../components/StepperLine'
import { useCover, useReceipt } from '../hooks/useMiniappData'
import { t } from '../lib/copy'
import { useMiniapp } from '../shell/MiniappContext'
import { Skeleton } from '../ui/skeleton'
import { ClaimsHeading } from './ClaimsHeading'
import { nextSteps, type NextStep } from './ClaimNextSteps'

function StepRow({ step, number }: { step: NextStep; number: number }) {
  return (
    <li data-testid={`claim-next-${step.id}`} data-step={step.id} className="flex items-start gap-3">
      <span aria-hidden="true" className="num flex size-6 shrink-0 items-center justify-center rounded-full bg-secondary text-xs font-medium text-ink-2">
        {number}
      </span>
      <div className="flex min-w-0 flex-col gap-0.5">
        <LineText line={step.line} className="text-sm text-foreground" />
        {step.note === null ? null : <LineText line={step.note} className="text-caption text-ink-2" />}
        {step.simulated === null ? null : <SimulatedLine kind={step.simulated} />}
      </div>
    </li>
  )
}

export function ClaimNextCard({ decisionId, canDispute }: { decisionId: string; canDispute: boolean }) {
  const { merchantId, lang } = useMiniapp()
  const receipt = useReceipt(merchantId, decisionId)
  const cover = useCover(merchantId)
  const shown = receipt.data?.decision.id === decisionId ? receipt.data : null
  if (shown === null) return receipt.state === 'loading' ? <Skeleton data-testid="claim-next-loading" className="h-40 w-full rounded-lg" /> : null
  const steps = nextSteps({ receipt: shown, cover: cover.data, canDispute }, lang)
  if (steps.length === 0) return null
  return (
    <section data-testid="claim-next-steps" className="flex flex-col gap-3 rounded-lg border bg-card p-4">
      <ClaimsHeading className="text-md font-bold">{t('claim.next.title', lang)}</ClaimsHeading>
      <ol className="flex flex-col gap-3">
        {steps.map((step, index) => (
          <StepRow key={step.id} step={step} number={index + 1} />
        ))}
      </ol>
    </section>
  )
}
