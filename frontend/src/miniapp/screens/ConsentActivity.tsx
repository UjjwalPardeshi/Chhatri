/**
 * N6 What was used (S11, `screen=consent-activity`, tab Help; fs-07 9.7 and 9.9, screens-and-flows 7.3). The log is a
 * projection of the audit log: one fixed sentence for each audit action, which the API writes and which never copies
 * text from the entry, so it cannot print a patient name. Purpose chips for the three purposes, "Show more" (the page
 * grows by one page), a link to the receipt of a decision, and "Check the log", which runs the audit chain check.
 * Times are replay times, and the footer says so.
 */
import { useState } from 'react'
import { useLocation } from 'react-router'

import { useLive } from '../../state/live'
import { CONSENT_PURPOSES, type ActivityItem, type ConsentPurpose } from '../api/rights'
import { ACTIVITY_PAGE } from '../api/rightsCalls'
import { tr, type RightsCopyKey } from '../copy/rights'
import { useActivity } from '../hooks/useRightsData'
import { t } from '../lib/copy'
import { cn } from '../lib/cn'
import { formatDateTime } from '../lib/format'
import { useMiniapp } from '../shell/MiniappContext'
import { EmptyState, NetworkButton, ResourceScreen } from '../shell/SharedStates'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { Card, CardContent } from '../ui/card'
import { Heading, useGoWithState, useRightsNba } from './rightsKit'

const FILTER_KEY: Readonly<Record<ConsentPurpose, RightsCopyKey>> = {
  SALES_DATA_FOR_CLAIM: 'activity.chip.sales',
  SLIP_DATA_FOR_HOSPITAL_CLAIM: 'activity.chip.slip',
  SETTLEMENT_DEDUCTION: 'activity.chip.settlement',
}
const DECISION_ID = /^D-\d{6,}$/

function purposeHint(state: unknown): ConsentPurpose | null {
  const purpose = typeof state === 'object' && state !== null ? (state as { purpose?: unknown }).purpose : null
  return typeof purpose === 'string' && (CONSENT_PURPOSES as readonly string[]).includes(purpose) ? (purpose as ConsentPurpose) : null
}

type LogCheck = { valid: boolean; entries: number; seq: number | null }

export function ConsentActivity() {
  const { lang, merchantId, url } = useMiniapp()
  const { api } = useLive()
  const go = useGoWithState()
  const { state: routeState } = useLocation()
  const [purpose, setPurpose] = useState<ConsentPurpose | null>(purposeHint(routeState))
  const [limit, setLimit] = useState(ACTIVITY_PAGE)
  const [check, setCheck] = useState<LogCheck | null>(null)
  const [checking, setChecking] = useState(false)
  const resource = useActivity(merchantId, purpose, limit)
  const ready = resource.state === 'ready' || resource.state === 'empty'
  useRightsNba(!ready ? null : { id: 'back_to_consents', sentence: 'nba.back_to_consents', button: 'nba.back_to_consents.btn', onAction: () => go(url.href({ screen: 'consents' })) })

  const runCheck = () => {
    setChecking(true)
    api
      .verifyAudit()
      .then((result) => setCheck({ valid: result.valid, entries: result.entries, seq: result.first_bad_seq }))
      .catch(() => setCheck(null))
      .finally(() => setChecking(false))
  }
  const choose = (next: ConsentPurpose | null) => {
    setPurpose(next)
    setLimit(ACTIVITY_PAGE)
  }
  const chip = (id: string, label: string, value: ConsentPurpose | null) => (
    <button key={id} type="button" data-testid={`activity-chip-${id}`} aria-pressed={purpose === value} onClick={() => choose(value)} className={cn('min-h-11 rounded-full border px-4 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50', purpose === value ? 'border-primary bg-primary text-primary-foreground' : 'bg-card text-foreground')}>
      {label}
    </button>
  )
  const row = (item: ActivityItem) => (
    <li key={`${item.seq}`} data-testid="activity-row" data-purpose={item.purpose} data-kind={item.kind}>
      <Card className="py-3">
        <CardContent className="flex flex-col gap-2 px-4">
          <div className="flex items-center justify-between gap-2 text-xs text-ink-3">
            <span>{formatDateTime(item.at, lang)}</span>
            <Badge variant="secondary">{tr(FILTER_KEY[item.purpose], lang)}</Badge>
          </div>
          <p className="text-sm">{lang === 'en' ? item.text_en : item.text_hi}</p>
          {item.ref?.type === 'decision' && DECISION_ID.test(item.ref.id) ? (
            <Button data-testid="activity-receipt" variant="outline" onClick={() => go(url.href({ screen: 'receipt', decision: item.ref?.id ?? '' }))}>
              {tr('consent.receipt', lang)}
            </Button>
          ) : null}
        </CardContent>
      </Card>
    </li>
  )
  /** The heading and the purpose chips stay in the empty state too, so a purpose with nothing in it can be switched back. */
  const header = (
    <>
      <Heading>{t('activity.title', lang)}</Heading>
      <fieldset className="m-0 flex min-w-0 flex-wrap gap-2 p-0">
        <legend className="sr-only">{t('activity.title', lang)}</legend>
        {chip('all', tr('activity.chip.all', lang), null)}
        {CONSENT_PURPOSES.map((id) => chip(id, tr(FILTER_KEY[id], lang), id))}
      </fieldset>
    </>
  )
  return (
    <ResourceScreen
      name="consent-activity"
      resource={resource}
      empty={
        <>
          {header}
          <EmptyState message={tr('activity.empty', lang)} />
        </>
      }
    >
      {(page) => (
        <>
          {header}
          <ul data-testid="activity-list" className="flex flex-col gap-2">
            {page.items.map(row)}
          </ul>
          {page.items.length < page.total ? (
            <NetworkButton data-testid="activity-more" variant="outline" onClick={() => setLimit(limit + ACTIVITY_PAGE)}>
              {tr('activity.more', lang)}
            </NetworkButton>
          ) : null}
          <NetworkButton data-testid="activity-check" variant="outline" disabled={checking} onClick={runCheck}>
            {tr('receipt.check_log', lang)}
          </NetworkButton>
          {check ? (
            <output data-testid="activity-check-result" className="text-sm">
              {check.valid ? tr('activity.log_ok', lang, { entries: check.entries }) : tr('activity.log_bad', lang, { seq: check.seq ?? 0 })}
            </output>
          ) : null}
          <p className="text-xs text-ink-3">{tr('activity.times', lang)}</p>
        </>
      )}
    </ResourceScreen>
  )
}
