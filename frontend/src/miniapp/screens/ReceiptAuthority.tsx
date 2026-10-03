/**
 * Who authorised the money (fs-04 S7, H3): the first block of the receipt, above the rows, so it is read before the
 * numbers. The policy engine decided, under the rules version the receipt names, or a claims officer did (the
 * receipt's `decided_by`); AI has no authority over a payout; and "Verify this decision" checks the audit log that
 * holds the decision. Every fact is read from the receipt, and the block decides nothing.
 */
import { ShieldCheck } from 'lucide-react'

import type { ReceiptDecision } from '../../api/types'
import { ReceiptRow } from '../components/ReceiptDocument'
import { t } from '../lib/copy'
import { useMiniapp } from '../shell/MiniappContext'
import { VerifyDecision } from './ReceiptAudit'
import { isOfficerDecision } from './ReceiptRows'

const ROW = 'py-2'

/** The engine in plain words, with the deck's line under it (code, not AI); an officer is named as the deck names one. */
function DecidedBy({ officer }: { officer: boolean }) {
  const { lang } = useMiniapp()
  if (officer) return <span className="block font-medium">{t('receipt.by.officer', lang)}</span>
  return (
    <>
      <span className="block font-medium">{t('receipt.authority.engine', lang)}</span>
      <span className="block text-caption text-ink-2">{t('receipt.by.engine', lang)}</span>
    </>
  )
}

export function ReceiptAuthority({ decision }: { decision: ReceiptDecision }) {
  const { lang, embedded } = useMiniapp()
  const Title = embedded ? 'h4' : 'h3'
  const officer = isOfficerDecision(decision)
  return (
    <section data-testid="receipt-authority" data-decided-by={officer ? 'officer' : 'engine'} className="flex flex-col gap-2 rounded-lg border bg-paper p-3 break-inside-avoid">
      <Title data-testid="receipt-authority-title" className="flex items-center gap-2 text-md font-bold text-foreground">
        <ShieldCheck className="size-4 shrink-0 text-decided" aria-hidden="true" />
        {t(decision.outcome === 'APPROVED' ? 'receipt.authority.title' : 'receipt.authority.title.record', lang)}
      </Title>
      <dl className="flex flex-col divide-y">
        <ReceiptRow label={t('receipt.row.decided_by', lang)} testId="receipt-decided-by" className={ROW}>
          <DecidedBy officer={officer} />
        </ReceiptRow>
        <ReceiptRow label={t('receipt.row.rules', lang)} className={ROW}>
          <span data-testid="receipt-rules-version" className="font-code">
            {decision.rules_version}
          </span>
        </ReceiptRow>
        <ReceiptRow label={t('receipt.authority.ai_label', lang)} testId="receipt-ai-authority" className={ROW}>
          {t('receipt.authority.ai', lang)}
        </ReceiptRow>
      </dl>
      <VerifyDecision />
    </section>
  )
}
