/**
 * The checks of a decision (fs-04 10.2): one row per check with its plain label by code, the result word and icon,
 * whether the check is HARD or SOFT, what the engine found and what it needed (its own English words), and the sources
 * of the check. Collapsed under one sentence when everything passed; open when a check failed, was unsure or was
 * cleared by an officer. Print shows what the screen shows (the button itself is left out), so a receipt of a clean
 * decision stays on one page, and a merchant who opened the list before printing gets the list on paper.
 */
import { ChevronDown, CircleCheck, CircleHelp, CircleX, Minus, ShieldCheck, type LucideIcon } from 'lucide-react'
import { useId, useState } from 'react'

import type { CheckStatus, ReceiptCheck } from '../../api/types'
import { SourceBadges } from '../components/SourceBadge'
import { langAttr } from '../components/StepperLine'
import { cn } from '../lib/cn'
import { t, type CopyKey } from '../lib/copy'
import { useMiniapp } from '../shell/MiniappContext'
import { Button } from '../ui/button'
import { summarise } from './ReceiptRows'

const STATUS_ICON: Readonly<Record<CheckStatus, LucideIcon>> = { PASS: CircleCheck, FAIL: CircleX, UNSURE: CircleHelp, NOT_APPLICABLE: Minus, WAIVED_BY_OFFICER: ShieldCheck }
const STATUS_TONE: Readonly<Record<CheckStatus, string>> = {
  PASS: 'bg-paid-soft text-paid-ink',
  FAIL: 'bg-blocked-soft text-blocked',
  UNSURE: 'bg-referred-soft text-referred-ink',
  NOT_APPLICABLE: 'bg-secondary text-secondary-foreground',
  WAIVED_BY_OFFICER: 'bg-referred-soft text-referred-ink',
}
const STATUS_KEY: Readonly<Record<CheckStatus, CopyKey>> = {
  PASS: 'chk.status.PASS',
  FAIL: 'chk.status.FAIL',
  UNSURE: 'chk.status.UNSURE',
  NOT_APPLICABLE: 'chk.status.NOT_APPLICABLE',
  WAIVED_BY_OFFICER: 'chk.status.WAIVED_BY_OFFICER',
}
const LABEL_KEYS: Readonly<Record<string, CopyKey>> = {
  COVER_IN_FORCE: 'CHK_COVER_IN_FORCE',
  PREMIUM_PREPAID: 'CHK_PREMIUM_PREPAID',
  COVER_BEFORE_ALERT: 'CHK_COVER_BEFORE_ALERT',
  ALERT_ACTIVE: 'CHK_ALERT_ACTIVE',
  INDEX_QUORUM: 'CHK_INDEX_QUORUM',
  BELOW_FLOOR: 'CHK_BELOW_FLOOR',
  BELOW_MODEL_RANGE: 'CHK_BELOW_MODEL_RANGE',
  SILENCE_VERIFIED: 'CHK_SILENCE_VERIFIED',
  SLIP_READABLE: 'CHK_SLIP_READABLE',
  NAME_MATCHES_KYC: 'CHK_NAME_MATCHES_KYC',
  DATES_MATCH: 'CHK_DATES_MATCH',
  WITHIN_AUTO_LIMIT: 'CHK_WITHIN_AUTO_LIMIT',
  NOT_ALREADY_PAID: 'CHK_NOT_ALREADY_PAID',
  WITHIN_ANNUAL_LIMIT: 'CHK_WITHIN_ANNUAL_LIMIT',
}

function CheckLabel({ check }: { check: ReceiptCheck }) {
  const { lang } = useMiniapp()
  const key = Object.hasOwn(LABEL_KEYS, check.code) ? LABEL_KEYS[check.code] : null
  return key === null ? <span lang={langAttr('en', lang)}>{check.label_en}</span> : <>{t(key, lang)}</>
}

/** What the engine found and needed, in its own English words: left out once the slip is erased, so nothing outlives it. */
function Findings({ check }: { check: ReceiptCheck }) {
  const { lang } = useMiniapp()
  if (check.erased || (check.observed === null && check.required === null)) return null
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
      {check.observed === null ? null : (
        <>
          <dt className="text-muted-foreground">{t('receipt.check.observed', lang)}</dt>
          <dd lang="en" className="num text-ink-2">{check.observed}</dd>
        </>
      )}
      {check.required === null ? null : (
        <>
          <dt className="text-muted-foreground">{t('receipt.check.required', lang)}</dt>
          <dd lang="en" className="num text-ink-2">{check.required}</dd>
        </>
      )}
    </dl>
  )
}

function CheckRow({ check, rulesVersion }: { check: ReceiptCheck; rulesVersion: string }) {
  const { lang } = useMiniapp()
  const Icon = STATUS_ICON[check.status]
  return (
    <li data-testid={`receipt-check-${check.code}`} data-status={check.status} data-severity={check.severity} className="flex flex-col gap-1.5 py-3 break-inside-avoid first:pt-0 last:pb-0">
      <div className="flex items-start justify-between gap-3">
        <p className="min-w-0 text-sm font-bold text-foreground">
          <CheckLabel check={check} />
        </p>
        <span className={cn('inline-flex shrink-0 items-center gap-1 rounded-sm px-1.5 py-0.5 text-xs font-bold', STATUS_TONE[check.status])}>
          <Icon className="size-3" aria-hidden="true" />
          {t(STATUS_KEY[check.status], lang)}
        </span>
      </div>
      <p lang="en" className="text-2xs tracking-wide text-ink-3">
        {check.severity}
      </p>
      <Findings check={check} />
      <SourceBadges sources={check.sources} rulesVersion={rulesVersion} />
    </li>
  )
}

export function ReceiptChecks({ checks, rulesVersion }: { checks: readonly ReceiptCheck[]; rulesVersion: string }) {
  const { lang } = useMiniapp()
  const summary = summarise(checks)
  const [open, setOpen] = useState(summary.needsLook)
  const listId = useId()
  if (checks.length === 0) return null
  return (
    <div data-testid="receipt-checks" data-open={open ? 'true' : 'false'} className="flex flex-col gap-2">
      {summary.allPassed ? <p className="text-sm text-foreground">{t('TRACK_CHECKED_OK', lang, { passed: summary.passed })}</p> : null}
      <Button
        type="button"
        variant="outline"
        data-testid="receipt-checks-toggle"
        aria-expanded={open}
        aria-controls={listId}
        className="h-auto min-h-11 w-fit py-2 print:hidden"
        onClick={() => setOpen((was) => !was)}
      >
        <ChevronDown className={cn('transition-transform', open && 'rotate-180')} aria-hidden="true" />
        {t(open ? 'receipt.checks.hide' : 'receipt.checks.show', lang)} ({checks.length})
      </Button>
      <ol id={listId} className={cn('flex-col divide-y', open ? 'flex' : 'hidden')}>
        {checks.map((check) => (
          <CheckRow key={check.code} check={check} rulesVersion={rulesVersion} />
        ))}
      </ol>
    </div>
  )
}
