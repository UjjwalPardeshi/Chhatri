/**
 * The audit entry of a decision (fs-04 10.2, AC-31): the first characters of the entry's hash, as a display choice,
 * and its place in the log. `VerifyDecision` is the "Verify this decision" action at the top of the receipt: "Check
 * the log" asks `GET /api/audit/verify` and shows how many entries the log holds when it is unbroken, or the first
 * entry that is broken. A broken log is never hidden. The button needs the network, so it is disabled with its reason
 * while offline; printing does not, and a result already on screen prints with the receipt.
 */
import { useCallback, useState } from 'react'

import type { AuditVerify, ReceiptAudit as Audit } from '../../api/types'
import { cn } from '../lib/cn'
import { t } from '../lib/copy'
import { useLive } from '../../state/live'
import { useMiniapp } from '../shell/MiniappContext'
import { NetworkButton } from '../shell/SharedStates'

type Check = { phase: 'idle' } | { phase: 'checking' } | { phase: 'failed' } | { phase: 'done'; result: AuditVerify }

function LogResult({ check }: { check: Check }) {
  const { lang } = useMiniapp()
  if (check.phase === 'idle' || check.phase === 'checking') return null
  if (check.phase === 'failed') {
    return (
      <p role="alert" data-testid="receipt-log-error" className="text-caption text-blocked">
        {t('error.generic', lang)}
      </p>
    )
  }
  const { valid, entries, first_bad_seq: seq } = check.result
  const text = valid ? t('receipt.log.ok', lang, { entries }) : t('receipt.log.broken', lang, { seq: seq ?? 0 })
  return (
    <output data-testid="receipt-log-result" data-valid={valid ? 'true' : 'false'} className={valid ? 'block text-caption font-medium text-paid-ink' : 'block text-caption font-medium text-blocked'}>
      {text}
    </output>
  )
}

export function ReceiptAudit({ audit }: { audit: Audit }) {
  return (
    <div className="flex flex-col items-start gap-2">
      <code data-testid="receipt-audit-prefix" className="font-code text-sm break-all text-foreground">
        {audit.hash_short}
      </code>
      <p className="text-caption text-ink-3">#{audit.seq}</p>
    </div>
  )
}

export function VerifyDecision() {
  const { lang } = useMiniapp()
  const { api } = useLive()
  const [check, setCheck] = useState<Check>({ phase: 'idle' })
  const run = useCallback(() => {
    setCheck({ phase: 'checking' })
    api
      .verifyAudit()
      .then((result) => setCheck({ phase: 'done', result }))
      .catch(() => setCheck({ phase: 'failed' }))
  }, [api])
  return (
    <div data-testid="receipt-verify" className={cn('flex flex-col items-start gap-1.5 border-t pt-3', check.phase !== 'done' && 'print:hidden')}>
      <div className="flex flex-col items-start gap-1.5 print:hidden">
        <p className="text-caption font-medium text-muted-foreground">{t('receipt.authority.verify', lang)}</p>
        <NetworkButton
          type="button"
          variant="outline"
          data-testid="receipt-check-log"
          className="h-auto min-h-11 py-2"
          disabled={check.phase === 'checking'}
          aria-busy={check.phase === 'checking' ? true : undefined}
          onClick={run}
        >
          {t('receipt.check_log', lang)}
        </NetworkButton>
      </div>
      <LogResult check={check} />
    </div>
  )
}
