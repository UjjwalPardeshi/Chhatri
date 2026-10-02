/**
 * S3 Buy (fs-04 section 8): ask for cover, see the truth, pay. One check asks the API for a quote (`POST /api/premium/link`):
 * BLOCKED says cover starts after the waiting period and that it will not pay for the alert in force, it never says
 * approved; the link is labelled SIMULATED and nothing is opened. The simulated payment posts the callback a real Paytm
 * would, then Home's cover is refetched and the new start date shown. A merchant who already has cover sees a status
 * card and no buy button. The price is only ever the API's (no number here); the check is disabled offline. With
 * `n6_consents` on, a merchant with no cover first reads the notice and ticks the two required boxes (fs-07 9.5): the
 * check stays disabled until both are ticked, the ticks and the notice version go with the quote call, and a 422 (the
 * notice changed) clears the ticks and reloads the consents.
 */
import { useState } from 'react'

import { ApiError } from '../../api/client'
import type { PremiumLinkResult } from '../../api/types'
import { isFeatureEnabled } from '../../features'
import type { Consent, ConsentPurpose } from '../api/rights'
import { CoverCard } from '../components/CoverCard'
import { useNextBest } from '../hooks/nextBestActionBar'
import { useClaims, useCover } from '../hooks/useMiniappData'
import { useResource, type Resource } from '../hooks/useResource'
import { useRules } from '../hooks/useRules'
import type { CopyKey } from '../lib/copy'
import { t } from '../lib/copy'
import { useLive } from '../../state/live'
import { useMiniapp } from '../shell/MiniappContext'
import { NetworkButton, ResourceScreen } from '../shell/SharedStates'
import { Skeleton } from '../ui/skeleton'
import { BuyConsent, firstUntickedBox } from './BuyConsent'
import { LinkCard, linkMode, PaidCard, QuoteCard } from './BuyResult'

type Phase = 'idle' | 'quoted' | 'paid'

const FIRST_DAYS_FALLBACK = 30

const NO_CONSENTS: Consent[] = []

function errorKeyOf(error: unknown): CopyKey {
  if (error instanceof ApiError && error.status === 422) return 'buy.consent.error'
  return error instanceof ApiError && (error.status === 401 || error.status === 403) ? 'buy.needs_presenter' : 'error.generic'
}

/** The three purposes of the consent block while `n6_consents` is on; nothing is asked with the flag off. */
function useBuyConsents(merchantId: string, on: boolean): Resource<Consent[]> {
  return useResource(merchantId, (api, signal) => (on ? api.consents(merchantId, signal) : Promise.resolve(NO_CONSENTS)), { deps: [on] })
}

function BuySkeleton() {
  const { lang } = useMiniapp()
  return (
    <output data-testid="app-skeleton" aria-label={t('state.loading', lang)} className="flex flex-col gap-3">
      <Skeleton className="h-5 w-3/4" />
      <Skeleton className="h-12 w-full" />
    </output>
  )
}

export function Buy() {
  const { merchantId, lang } = useMiniapp()
  const { api } = useLive()
  const cover = useCover(merchantId)
  const claims = useClaims(merchantId)
  const rules = useRules()
  const [result, setResult] = useState<PremiumLinkResult | null>(null)
  const [phase, setPhase] = useState<Phase>('idle')
  const [busy, setBusy] = useState(false)
  const [errorKey, setErrorKey] = useState<CopyKey | null>(null)
  const consentOn = isFeatureEnabled('n6_consents')
  const consents = useBuyConsents(merchantId, consentOn)
  const [ticked, setTicked] = useState<ReadonlySet<ConsentPurpose>>(new Set())

  const premium = result?.premium ?? null
  const shown = (cover.state === 'ready' || cover.state === 'offline') && cover.data !== null
  const purposes = consents.data ?? NO_CONSENTS
  const needsBlock = consentOn && cover.data?.status === 'NONE' && phase === 'idle'
  /** The block shows once the purposes are known; until then the check waits. If they cannot be read the server decides. */
  const asking = needsBlock && purposes.length > 0
  const waitingForBlock = needsBlock && consents.data === null && consents.error === null
  const firstUnticked = asking ? firstUntickedBox(purposes, ticked) : null
  const consentState = asking ? { consent: { firstUnticked } } : {}
  useNextBest(shown && cover.data && claims.state !== 'loading' ? { screen: 'buy', cover: cover.data, claims: claims.data ?? [], buy: { phase, simulated: premium === null || linkMode(premium) === 'SIMULATED', ...consentState } } : null)

  function toggle(purpose: ConsentPurpose, on: boolean): void {
    setTicked((before) => {
      const next = new Set(before)
      if (on) next.add(purpose)
      else next.delete(purpose)
      return next
    })
  }

  async function check(): Promise<void> {
    setBusy(true)
    setErrorKey(null)
    try {
      const consent = asking ? { consents: [...ticked], notice_version: purposes[0]?.current_notice_version ?? '' } : undefined
      const next = await api.premiumLink(merchantId, consent)
      if (next.premium === null) {
        setErrorKey('buy.link_unavailable')
        return
      }
      setResult(next)
      setPhase('quoted')
    } catch (error: unknown) {
      setErrorKey(errorKeyOf(error))
      if (error instanceof ApiError && error.status === 422) {
        setTicked(new Set())
        consents.reload()
      }
    } finally {
      setBusy(false)
    }
  }

  async function simulatePay(): Promise<void> {
    if (!premium?.link_id) return
    setBusy(true)
    setErrorKey(null)
    try {
      await api.paytmWebhook(premium.link_id)
      setPhase('paid')
      cover.reload()
    } catch {
      setErrorKey('error.pay_failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <ResourceScreen name="buy" resource={cover} skeleton={<BuySkeleton />}>
      {(data) => {
        const covered = data.status !== 'NONE' && phase === 'idle'
        return (
          <>
            {covered ? <CoverCard cover={data} testPrefix="buy" /> : null}
            {covered ? null : phase === 'paid' && premium ? <PaidCard premium={premium} lang={lang} /> : (
              <>
                <p className="text-md">{t('buy.intro', lang, { waiting_days: rules.data?.waiting_period_days ?? '' })}</p>
                {asking ? <BuyConsent consents={purposes} ticked={ticked} lang={lang} disabled={busy} onToggle={toggle} /> : null}
                {phase === 'idle' ? (
                  <NetworkButton data-testid="buy-check" size="lg" disabled={busy || waitingForBlock || firstUnticked !== null} onClick={() => void check()}>
                    {t('buy.check', lang)}
                  </NetworkButton>
                ) : null}
              </>
            )}
            {errorKey ? (
              <p data-testid={errorKey === 'buy.consent.error' ? 'buy-consent-error' : 'buy-error'} role="alert" className="rounded-lg border border-blocked bg-blocked-soft p-3 text-sm">
                {t(errorKey, lang)}
              </p>
            ) : null}
            {phase !== 'idle' && result ? <QuoteCard quote={result.quote} lang={lang} firstDays={result.quote.days_prepaid || FIRST_DAYS_FALLBACK} /> : null}
            {phase === 'quoted' && premium ? <LinkCard premium={premium} lang={lang} busy={busy} onSimulate={() => void simulatePay()} /> : null}
          </>
        )
      }}
    </ResourceScreen>
  )
}
