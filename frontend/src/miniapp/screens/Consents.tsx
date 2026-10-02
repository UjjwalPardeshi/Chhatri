/**
 * N6 My data and consent (S10, `screen=consents`, tab Help; fs-07 9.9, screens-and-flows 7.2). One card for each of the
 * three purposes, in the API's fixed order. The switch opens the withdraw sheet and flips when the call succeeds; a
 * slip is erased through its own sheet after its claim review is answered. Nothing here edits a decision, a payout or
 * the audit log, and the screen says so where it matters. A merchant with no cover sees the empty state and the way to
 * get cover. Writes need the network and the demo's officer session, like the payment link.
 */
import { useCallback, useState } from 'react'
import { toast } from 'sonner'

import { ApiError } from '../../api/client'
import { isFeatureEnabled } from '../../features'
import { useLive } from '../../state/live'
import type { Consent, HeldSlip } from '../api/rights'
import { tr, type RightsCopyKey } from '../copy/rights'
import { useConsents } from '../hooks/useRightsData'
import { t } from '../lib/copy'
import { useMiniapp } from '../shell/MiniappContext'
import { EmptyState, ResourceScreen } from '../shell/SharedStates'
import { Button } from '../ui/button'
import { ConsentCard } from './ConsentCard'
import { EraseSheet, WithdrawSheet } from './ConsentSheets'
import { Heading, useGoWithState, useRightsNba } from './rightsKit'

const WITHDRAW_ERRORS: Readonly<Record<string, RightsCopyKey>> = { case_open: 'consent.err.case_open', already_withdrawn: 'consent.err.already_withdrawn' }
const ERASE_ERRORS: Readonly<Record<string, RightsCopyKey>> = { case_open: 'slip.erase.blocked', already_erased: 'slip.erase.err.already_erased' }

function refusal(error: unknown, known: Readonly<Record<string, RightsCopyKey>>): RightsCopyKey | null {
  return error instanceof ApiError ? (known[error.code] ?? null) : null
}

export function Consents() {
  const { lang, merchantId, url, online } = useMiniapp()
  const { api } = useLive()
  const go = useGoWithState()
  const resource = useConsents(merchantId)
  const { reload } = resource
  const [withdrawing, setWithdrawing] = useState<Consent | null>(null)
  const [erasing, setErasing] = useState<HeldSlip | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<RightsCopyKey | null>(null)

  const close = useCallback(() => {
    setWithdrawing(null)
    setErasing(null)
    setError(null)
  }, [])

  const settle = useCallback(
    (action: () => Promise<unknown>, done: string, known: Readonly<Record<string, RightsCopyKey>>) => {
      setBusy(true)
      setError(null)
      action()
        .then(() => {
          toast(done)
          close()
        })
        .catch((failure: unknown) => {
          const reason = refusal(failure, known)
          if (reason) setError(reason)
          else {
            toast.error(t('error.generic', lang))
            close()
          }
        })
        .finally(() => {
          setBusy(false)
          reload()
        })
    },
    [lang, close, reload],
  )

  const confirmWithdraw = () => withdrawing?.consent_id && settle(() => api.withdrawConsent(merchantId, withdrawing.consent_id ?? ''), tr('consent.withdraw.done', lang), WITHDRAW_ERRORS)
  const confirmErase = () => erasing && settle(() => api.forgetSlip(merchantId, erasing.slip_id), tr('slip.erase.done', lang), ERASE_ERRORS)
  const toActivity = (purpose?: string) => go(url.href({ screen: 'consent-activity' }), purpose ? { purpose } : undefined)

  const list = resource.data
  const hasCover = list !== null && list.some((c) => c.status !== 'NOT_GIVEN')
  const ready = resource.state === 'ready' || resource.state === 'empty'
  useRightsNba(!ready ? null : hasCover ? { id: 'see_activity', sentence: 'nba.see_activity', button: 'nba.see_activity.btn', onAction: () => toActivity() } : { id: 'get_cover_from_consents', sentence: 'nba.get_cover_from_consents', button: 'nba.get_cover_from_consents.btn', onAction: () => go(url.href({ screen: 'buy' })) })

  const actions = { disabled: busy || !online, onWithdraw: (consent: Consent) => { setError(null); setWithdrawing(consent) }, onErase: (slip: HeldSlip) => { setError(null); setErasing(slip) }, onReceipt: (consent: Consent) => toActivity(consent.purpose) }
  return (
    <>
      <ResourceScreen
        name="consents"
        resource={resource}
        empty={
          <EmptyState message={tr('consent.empty', lang)}>
            <Button data-testid="consent-get-cover" onClick={() => go(url.href({ screen: 'buy' }))}>
              {tr('nba.get_cover_from_consents.btn', lang)}
            </Button>
          </EmptyState>
        }
      >
        {(consents) => (
          <>
            <Heading>{t('consent.title', lang)}</Heading>
            <p className="text-sm text-ink-2">{tr('consent.intro', lang)}</p>
            {consents.map((consent) => (
              <ConsentCard key={consent.purpose} consent={consent} lang={lang} actions={actions} />
            ))}
            <div className="flex flex-col gap-2">
              <Button data-testid="consent-activity-link" variant="outline" onClick={() => toActivity()}>
                {tr('consent.activity_link', lang)}
              </Button>
              {isFeatureEnabled('n5_grievances') ? (
                <Button data-testid="consent-complain" variant="outline" onClick={() => go(url.href({ screen: 'grievances' }), { topic: 'DATA_OR_CONSENT' })}>
                  {tr('consent.complain', lang)}
                </Button>
              ) : null}
            </div>
            <p data-testid="consent-version" className="text-xs text-ink-3">
              {tr('consent.version', lang, { version: consents[0].current_notice_version })}
            </p>
          </>
        )}
      </ResourceScreen>
      {withdrawing ? <WithdrawSheet lang={lang} busy={busy} error={error} effect={lang === 'en' ? withdrawing.withdraw_effect_en : withdrawing.withdraw_effect_hi} onClose={close} onConfirm={confirmWithdraw} /> : null}
      {erasing ? <EraseSheet lang={lang} busy={busy} error={error} onClose={close} onConfirm={confirmErase} /> : null}
    </>
  )
}
