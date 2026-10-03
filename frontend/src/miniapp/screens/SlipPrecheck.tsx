/**
 * N3 slip pre-check (fs-02 7.3, screens-and-flows 6): the merchant sends one photo of the hospital slip, sees what was
 * read, and confirms it, sends another photo or sends it to the team. No claim is decided until then, and the engine
 * alone decides after. A photo that cannot be used is a plain sentence with the next step, never a dead end; at most
 * three photos per check-in. The sheet carries the H26 label (LIVE, SIMULATED or FALLBACK) and never a confidence
 * number. It exists only behind `n3_slip_precheck` (the URL does not know the screen while the flag is off). With
 * `n6_consents` on and no ACTIVE slip consent, one unticked box asks for the OK first (fs-07 9.3); the OK goes with
 * the photo and the server records it before it reads anything. After "Yes, this is right" the doctor question follows
 * (design 2.4): Yes or No, and the claim opens. Opening the sheet resumes what the open check-in waits on.
 */
import { useRef, useState, type ChangeEvent } from 'react'

import type { PrecheckConsent } from '../../api/types'
import { isFeatureEnabled } from '../../features'
import { useLive } from '../../state/live'
import type { Consent } from '../api/rights'
import { useResource } from '../hooks/useResource'

import { useNextBest } from '../hooks/nextBestActionBar'
import { t } from '../lib/copy'
import { useMiniapp } from '../shell/MiniappContext'
import { ScreenRoot } from '../shell/SharedStates'
import { Button } from '../ui/button'
import { Skeleton } from '../ui/skeleton'
import { MAX_MB, slipPossible, useSlipPrecheckFlow, type FlowState } from './SlipPrecheckFlow'
import { ConsentStep, SlipActions, SlipChecklist, SlipFields, SlipFooter, SlipNotes } from './SlipPrecheckParts'

const BLURRY_SAMPLE = 'blurry_slip.png'
const NO_CONSENTS: Consent[] = []

/** The slip consent while `n6_consents` is on: the OK to send, or null when none is needed. `blocked` until it is ticked. */
function useSlipOk(merchantId: string): { needed: boolean; ticked: boolean; setTicked: (on: boolean) => void; ok: PrecheckConsent } {
  const on = isFeatureEnabled('n6_consents')
  const consents = useResource(merchantId, (api, signal) => (on ? api.consents(merchantId, signal) : Promise.resolve(NO_CONSENTS)), { deps: [on] })
  const [ticked, setTicked] = useState(false)
  const slip = consents.data?.find((c) => c.purpose === 'SLIP_DATA_FOR_HOSPITAL_CLAIM') ?? null
  const needed = on && slip !== null && slip.status !== 'ACTIVE'
  const ok: PrecheckConsent = needed && ticked && slip ? { consent: true, notice_version: slip.current_notice_version } : {}
  return { needed, ticked, setTicked, ok }
}

function ErrorLine({ state, lang }: { state: FlowState; lang: 'hi' | 'en' | 'mr' }) {
  if (!state.errorKey) return null
  return (
    <p data-testid="slip-error" role="alert" className="rounded-lg border border-blocked bg-blocked-soft p-3 text-sm">
      {t(state.errorKey, lang, { max_mb: MAX_MB })}
    </p>
  )
}

export function SlipPrecheck() {
  const { merchantId, lang, online, url } = useMiniapp()
  const camera = useRef<HTMLInputElement>(null)
  const gallery = useRef<HTMLInputElement>(null)
  const { state, sendFile, sendSample, decide, cancel } = useSlipPrecheckFlow(
    merchantId,
    lang === 'mr' ? undefined : lang,
    (claimId) => url.go({ screen: 'claim', claim: claimId }),
  )
  useNextBest(null)
  const slipOk = useSlipOk(merchantId)
  const waitingForOk = slipOk.needed && !slipOk.ticked

  const { snapshot } = useLive()
  const { phase, check, consent } = state
  const busy = phase === 'reading' || phase === 'deciding'

  if (!check && !slipPossible(snapshot?.clock.scenario)) {
    return (
      <ScreenRoot name="slip" state="ready">
        <p data-testid="slip-none" className="text-md">{t('slip.none', lang)}</p>
        <Button data-testid="slip-none-home" variant="outline" size="lg" onClick={() => url.go({ screen: 'home' })}>
          {t('slip.none.home', lang)}
        </Button>
      </ScreenRoot>
    )
  }

  function picked(event: ChangeEvent<HTMLInputElement>): void {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (file) sendFile(file, slipOk.ok)
  }

  const inputs = (
    <>
      <input ref={camera} data-testid="slip-camera-input" type="file" accept="image/*" capture="environment" hidden onChange={picked} />
      <input ref={gallery} data-testid="slip-gallery-input" type="file" accept="image/*" hidden onChange={picked} />
    </>
  )

  if (consent && (phase === 'consent' || phase === 'deciding')) {
    return (
      <ScreenRoot name="slip" state={online ? 'ready' : 'offline'}>
        <ConsentStep consent={consent} lang={lang} busy={busy} online={online} onAnswer={(yes) => void decide(yes ? 'CONSENT_YES' : 'CONSENT_NO')} />
        <ErrorLine state={state} lang={lang} />
        {phase === 'deciding' ? <p data-testid="slip-deciding" className="text-sm text-ink-2">{t('slip.working', lang)}</p> : null}
        {online ? null : <p className="text-xs text-ink-3">{t('offline.blocked', lang)}</p>}
      </ScreenRoot>
    )
  }

  if (phase === 'reading' || phase === 'deciding') {
    const reading = phase === 'reading'
    return (
      <ScreenRoot name="slip" state="loading">
        <output data-testid={reading ? 'slip-reading' : 'slip-deciding'} className="flex flex-col gap-3">
          <p className="text-md">{t(reading ? 'SLIP_READING' : 'slip.working', lang)}</p>
          <Skeleton className="h-24 w-full" />
        </output>
        {reading ? (
          <Button data-testid="slip-cancel" variant="outline" size="lg" onClick={cancel}>
            {t('slip.cancel', lang)}
          </Button>
        ) : null}
      </ScreenRoot>
    )
  }

  if (check) {
    const ready = check.status === 'READY'
    return (
      <ScreenRoot name="slip" state={online ? 'ready' : 'offline'}>
        {inputs}
        <section data-testid="slip-result" data-status={check.status} data-attempt={check.attempt} className="flex flex-col gap-4">
          {ready ? <p className="text-md">{t('SLIP_PRECHECK_SHOW', lang)}</p> : null}
          {check.guidance ? (
            <output data-testid="slip-guidance" className="rounded-lg border border-referred bg-referred-soft p-3 text-md text-referred-ink">
              {t(check.guidance.key, lang)}
            </output>
          ) : null}
          {ready ? null : <h3 className="text-sm font-medium text-ink-2">{t('slip.what_read', lang)}</h3>}
          <SlipFields slots={check.slots} lang={lang} muted={!ready} />
          <SlipChecklist lines={check.checklist} lang={lang} />
          <SlipNotes check={check} lang={lang} />
        </section>
        <ErrorLine state={state} lang={lang} />
        <SlipActions
          check={check}
          lang={lang}
          busy={busy}
          online={online}
          onConfirm={() => void decide('CONFIRM')}
          onRetake={() => camera.current?.click()}
          onTeam={() => void decide('SEND_TO_TEAM')}
        />
        {online ? null : <p className="text-xs text-ink-3">{t('offline.blocked', lang)}</p>}
        <SlipFooter check={check} lang={lang} />
      </ScreenRoot>
    )
  }

  return (
    <ScreenRoot name="slip" state={online ? 'ready' : 'offline'}>
      {inputs}
      <p className="text-md">{t('SLIP_SHEET_HELP', lang)}</p>
      <ErrorLine state={state} lang={lang} />
      {slipOk.needed ? (
        <div className="flex min-h-11 items-start gap-3 rounded-lg border bg-card p-3">
          <input
            id="slip-consent"
            data-testid="slip-consent"
            type="checkbox"
            className="mt-1 size-5 shrink-0 accent-primary"
            checked={slipOk.ticked}
            onChange={(event) => slipOk.setTicked(event.target.checked)}
          />
          <label htmlFor="slip-consent" className="text-sm">
            {t('buy.consent.box.SLIP_DATA_FOR_HOSPITAL_CLAIM', lang)}
          </label>
        </div>
      ) : null}
      <div className="flex flex-col gap-2">
        <Button data-testid="slip-take" size="lg" disabled={!online || waitingForOk} onClick={() => camera.current?.click()}>
          {t('slip.take_photo', lang)}
        </Button>
        <Button data-testid="slip-gallery" size="lg" variant="outline" disabled={!online || waitingForOk} onClick={() => gallery.current?.click()}>
          {t('slip.choose_gallery', lang)}
        </Button>
        {online ? null : <p className="text-xs text-ink-3">{t('offline.blocked', lang)}</p>}
      </div>
      <p data-testid="slip-notice" className="text-sm text-ink-2">{t('SLIP_NOTICE', lang)}</p>
      <p data-testid="slip-sim" className="rounded-lg bg-demo-soft px-3 py-2 text-xs text-demo">{t('sim.slip', lang)}</p>
      <section aria-labelledby="slip-demo-title" className="flex flex-col gap-2 border-t pt-3">
        <h3 id="slip-demo-title" className="text-sm font-medium text-ink-2">{t('slip.demo.title', lang)}</h3>
        <Button data-testid="slip-demo-good" variant="outline" disabled={!online || waitingForOk} onClick={() => sendSample(undefined, slipOk.ok)}>
          {t('slip.demo.good', lang)}
        </Button>
        <Button data-testid="slip-demo-blurry" variant="outline" disabled={!online || waitingForOk} onClick={() => sendSample(BLURRY_SAMPLE, slipOk.ok)}>
          {t('slip.demo.blurry', lang)}
        </Button>
      </section>
    </ScreenRoot>
  )
}
