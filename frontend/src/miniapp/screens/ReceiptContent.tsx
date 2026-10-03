/**
 * What the receipt says (fs-04 S7, 10.2, screens and flows 4.7): the SIMULATED line, then one card led by who
 * authorised the money (the engine under its rules version, or an officer; no AI; "Verify this decision"), then the
 * decision and when it was made, the formula, where each number came from, the checks, what would have changed it, the
 * clauses used, the payout and the lender's answer, the audit entry and the way up if the merchant disagrees.
 * Everything is read from the receipt, and the app computes none of it. A row that has nothing to say is not drawn.
 * A number with no source reads "Source missing" (the parser refuses such a receipt, and this is the second net).
 */
import { Fragment } from 'react'

import type { Receipt } from '../../api/types'
import { CounterfactualCard } from '../components/CounterfactualCard'
import { FormulaBlock } from '../components/FormulaBlock'
import { ReceiptDocument, ReceiptNotice, ReceiptRow } from '../components/ReceiptDocument'
import { SourceBadges, clauseTitle } from '../components/SourceBadge'
import { SimulatedLine } from '../components/Stepper'
import { LineText } from '../components/StepperLine'
import { t } from '../lib/copy'
import { formatDateTime } from '../lib/format'
import { useMiniapp } from '../shell/MiniappContext'
import { Badge } from '../ui/badge'
import { ReceiptAudit } from './ReceiptAudit'
import { ReceiptAuthority } from './ReceiptAuthority'
import { ClaimsHeading } from './ClaimsHeading'
import { ReceiptChecks } from './ReceiptChecks'
import { ReceiptLadder } from './ReceiptLadder'
import { clausesOf, isCredited, isOfficerDecision, isSimulated, lenderLine } from './ReceiptRows'
import { rowLabel, rowValue, whyRows } from './WhyRows'

function DecisionRow({ receipt }: { receipt: Receipt }) {
  const { lang } = useMiniapp()
  const { decision } = receipt
  const officer = isOfficerDecision(decision)
  const word =
    decision.outcome === 'REFERRED'
      ? t('claim.status.referred', lang)
      : decision.outcome === 'DECLINED'
        ? t('claim.status.declined', lang)
        : officer
          ? t('TRACK_DECIDED_OFFICER', lang)
          : t('TRACK_DECIDED_AUTO', lang, { amount: decision.amount_label })
  return (
    <ReceiptRow label={t('receipt.row.decision', lang)} testId="receipt-decision">
      <span className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span data-testid="receipt-decision-id" className="font-code">
          {decision.id}
        </span>
        <span data-testid="receipt-outcome" data-outcome={decision.outcome} className="font-medium">
          {word}
        </span>
        {decision.outcome === 'APPROVED' && officer ? (
          <span data-testid="receipt-amount" className="num font-medium">
            {decision.amount_label}
          </span>
        ) : null}
      </span>
    </ReceiptRow>
  )
}

function SourcesRow({ receipt }: { receipt: Receipt }) {
  const { lang } = useMiniapp()
  const rows = whyRows(receipt.explanation.facts)
  if (rows.length === 0) return null
  return (
    <ReceiptRow label={t('receipt.row.sources', lang)} testId="receipt-sources">
      <ul className="flex flex-col gap-3">
        {rows.map((row) => {
          const label = rowLabel(row, lang)
          return (
            <li key={row.key} data-testid={`receipt-source-${row.key}`} className="flex flex-col gap-1">
              <p className="text-caption text-ink-2">
                <span lang={label.lang}>{label.text}</span>: <span className="num font-medium text-foreground">{rowValue(row.value, lang)}</span>
              </p>
              <SourceBadges sources={row.sources} rulesVersion={receipt.decision.rules_version} />
            </li>
          )
        })}
      </ul>
    </ReceiptRow>
  )
}

function ClausesRow({ receipt }: { receipt: Receipt }) {
  const { lang } = useMiniapp()
  const clauses = clausesOf(receipt)
  if (clauses.length === 0) return null
  return (
    <ReceiptRow label={t('receipt.row.clauses', lang)} testId="receipt-clauses">
      <ul className="flex flex-wrap gap-2">
        {clauses.map((clause) => {
          const title = clauseTitle(clause, lang)
          return (
            <li key={clause}>
              <Badge variant="outline" className="h-auto min-h-6 gap-1 py-1 whitespace-normal print:border-line-strong">
                <span className="font-medium">{clause}</span>
                {title === null ? null : <span className="text-ink-2 print:hidden">· {title}</span>}
              </Badge>
            </li>
          )
        })}
      </ul>
    </ReceiptRow>
  )
}

function PayoutRow({ receipt }: { receipt: Receipt }) {
  const { lang } = useMiniapp()
  const { payout, decision } = receipt
  if (isCredited(receipt) && payout !== null) {
    return (
      <ReceiptRow label={t('receipt.row.paid_at', lang)} testId="receipt-payout">
        <span className="num">{formatDateTime(payout.credited_at, lang)}</span>
        <SimulatedLine kind="payment" />
      </ReceiptRow>
    )
  }
  return decision.outcome === 'APPROVED' ? (
    <ReceiptRow label={t('receipt.row.payout', lang)} testId="receipt-payout">
      {t('receipt.row.pending', lang)}
    </ReceiptRow>
  ) : null
}

function LenderRow({ receipt }: { receipt: Receipt }) {
  const { lang } = useMiniapp()
  if (receipt.edi === null) return null
  return (
    <ReceiptRow label={t('receipt.row.lender', lang)} testId="receipt-lender">
      <LineText line={lenderLine(receipt.edi, lang)} />
      <SimulatedLine kind="lender" />
    </ReceiptRow>
  )
}

export function ReceiptContent({ receipt }: { receipt: Receipt }) {
  const { lang } = useMiniapp()
  const { decision, explanation, checks, counterfactuals, audit, grievance } = receipt
  const credited = isCredited(receipt)
  return (
    <Fragment>
      <p data-testid="receipt-print-header" className="hidden text-center text-md font-medium print:block">
        {t('receipt.print.header', lang)}
      </p>
      {isSimulated(receipt) ? (
        <ReceiptNotice testId="receipt-simulated" tone="demo">
          {t('receipt.simulated', lang)}
        </ReceiptNotice>
      ) : null}
      {credited ? null : (
        <ReceiptNotice testId="receipt-pending-note" tone="neutral">
          {t('empty.receipt', lang)}
        </ReceiptNotice>
      )}
      <ReceiptDocument
        heading={
          <ClaimsHeading data-testid="receipt-heading" className={credited ? 'sr-only' : 'text-md font-medium'}>
            {t(credited ? 'receipt.title' : 'receipt.title.record', lang)}
          </ClaimsHeading>
        }
        lead={<ReceiptAuthority decision={decision} />}
      >
        <DecisionRow receipt={receipt} />
        <ReceiptRow label={t('receipt.row.decided_at', lang)}>
          <time dateTime={decision.decided_at} className="num">
            {formatDateTime(decision.decided_at, lang)}
          </time>
        </ReceiptRow>
        {decision.outcome === 'APPROVED' ? (
          <ReceiptRow label={t('receipt.row.formula', lang)} testId="receipt-formula-row">
            <FormulaBlock testId="receipt-formula" en={explanation.formula_en} hi={explanation.formula_hi} />
          </ReceiptRow>
        ) : null}
        {decision.outcome === 'APPROVED' ? <SourcesRow receipt={receipt} /> : null}
        {checks.length === 0 ? null : (
          <ReceiptRow label={t('receipt.row.checks', lang)} testId="receipt-checks-row">
            <ReceiptChecks checks={checks} rulesVersion={decision.rules_version} />
          </ReceiptRow>
        )}
        {counterfactuals.length === 0 ? null : (
          <ReceiptRow label={t('receipt.row.what_changes', lang)} testId="receipt-what-changes">
            <CounterfactualCard items={counterfactuals} testId="receipt-counterfactual" untitled />
          </ReceiptRow>
        )}
        <ClausesRow receipt={receipt} />
        <PayoutRow receipt={receipt} />
        <LenderRow receipt={receipt} />
        <ReceiptRow label={t('receipt.row.audit', lang, { n: audit.hash_short.length })} testId="receipt-audit">
          <ReceiptAudit audit={audit} />
        </ReceiptRow>
        <ReceiptRow label={t('receipt.row.disagree', lang)} testId="receipt-disagree">
          <ReceiptLadder grievance={grievance} />
        </ReceiptRow>
      </ReceiptDocument>
    </Fragment>
  )
}
