/**
 * Merchant phone page (SPEC §13, §20 "Merchant phone"): the WhatsApp-like conversation for one
 * merchant, updated live from `message` events, with the shop's Soundbox, money and the "What
 * happened" steps beside it. With telegram_channel on, a switch beside it moves the merchant's
 * messages to Telegram, and the phone then wears Telegram's colours; under it the officer's card gives the treating
 * doctor's Telegram enrolment link (DoctorLinkCard).
 * A launcher from the Overview can pass a `hint` (useLaunch) to highlight the chip to tap next.
 */
import { lazy, Suspense, useCallback, useMemo, useState } from 'react'
import { useLocation, useParams } from 'react-router'

import { assertMerchantId } from '../api/endpoints'
import type { Message, VoiceDemoKey } from '../api/types'
import { Feature } from '../components/common/Feature'
import { ErrorState, InlineError, Loading } from '../components/common/Status'
import { ChannelSwitch } from '../components/phone/ChannelSwitch'
import { DoctorLinkCard } from '../components/phone/DoctorLinkCard'
import { Composer, type ComposerActions } from '../components/phone/Composer'
import { MerchantPanel } from '../components/phone/MerchantPanel'
import { coverOffer } from '../components/phone/coverOffer'
import { chatMessages, latestSoundbox, upsertMessage, voiceAudioUrl } from '../components/phone/messages'
import { Phone } from '../components/phone/Phone'
import { SoundboxDevice } from '../components/phone/SoundboxDevice'
import { SoundboxStrip } from '../components/phone/SoundboxStrip'
import { happenedSteps } from '../components/phone/whatHappened'
import { ApiError } from '../api/client'
import { isFeatureEnabled } from '../features'
import { useLive, useLiveEvent } from '../state/live'
import { toApiError, useAsync } from '../state/useAsync'
import type { LaunchNavState } from '../state/useLaunch'
import { useChannel } from '../state/useChannel'
import { useDoctorLinks } from '../state/useDoctorLinks'
import { useMerchant } from '../state/useMerchant'
import { useSettle } from '../state/useSettle'

const PULSE_MS = 2_400

/** The mini-app frame (card 3.7): its chunk is requested only when the flag n1_miniapp is on and this page renders it. */
const AppFrame = lazy(() => import('../miniapp/shell/AppFrame'))

function validId(raw: string | undefined): string | null {
  try {
    return raw ? assertMerchantId(raw) : null
  } catch {
    return null
  }
}

function useConversation(merchantId: string) {
  const { api, snapshot, sound } = useLive()
  const scenarioKey = `${snapshot?.clock.scenario}|${snapshot?.clock.start}`
  const [version, setVersion] = useState(0)
  const loaded = useAsync((signal) => api.messages(merchantId, signal), [api, merchantId, scenarioKey, version])
  const base = loaded.data
  /** Live messages received since `base` was fetched; a fresh fetch already contains them. */
  const [live, setLive] = useState<{ base: Message[] | null; items: Message[] }>({ base: null, items: [] })
  const messages = useMemo(() => {
    const extra = live.base === base ? live.items : []
    return [...(base ?? []), ...extra].reduce<Message[]>((list, m) => upsertMessage(list, m), [])
  }, [base, live])
  const [pulse, setPulse] = useState(false)
  useLiveEvent(['message', 'soundbox'], (event) => {
    if (event.type === 'soundbox' && event.data.merchant_id === merchantId) {
      setPulse(true)
      setTimeout(() => setPulse(false), PULSE_MS)
    }
    if (event.type !== 'message' || event.data.message.merchant_id !== merchantId) return
    const message = event.data.message
    setLive((current) => ({ base, items: [...(current.base === base ? current.items : []), message] }))
    if (message.direction === 'OUTBOUND' && message.channel !== 'SOUNDBOX' && message.text_hi) void sound.autoPlay(message.text_hi, voiceAudioUrl(message))
  })
  const reload = useCallback(() => setVersion((v) => v + 1), [])
  return { messages, loaded, pulse, reload }
}

/**
 * Phone actions. A slip photo can approve a personal claim; on a paused replay the clock then
 * steps to the end of the payout workflow so the ₹1,500 card arrives on screen (useSettle, B2).
 */
function useActions(merchantId: string, reload: () => void) {
  const { api } = useLive()
  const settle = useSettle()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const run = async (action: () => Promise<unknown>, settles = false): Promise<boolean> => {
    setBusy(true)
    try {
      await action()
      if (settles) await settle(merchantId)
      setError(null)
      return true
    } catch (reason) {
      setError(toApiError(reason))
      return false
    } finally {
      setBusy(false)
      reload()
    }
  }
  const actions: ComposerActions = {
    sendText: (text) => run(() => api.sendText(merchantId, text)),
    sendVoiceDemo: (key: VoiceDemoKey) => run(() => api.sendVoiceDemo(merchantId, key)),
    sendVoice: (blob, filename) => run(() => api.sendVoice(merchantId, blob, filename)),
    sendPhoto: (file) => run(() => api.sendPhoto(merchantId, file), true),
    sendSample: (file) => run(() => api.sendSampleSlip(merchantId, file), true),
  }
  return { actions, busy, error, clearError: () => setError(null) }
}

/** The chip a launcher asked to highlight (LaunchNavState), if any. */
function useHint(): string | null {
  const state = useLocation().state as Partial<LaunchNavState> | null
  return typeof state?.hint === 'string' ? state.hint : null
}

function MerchantView({ merchantId }: { merchantId: string }) {
  const { snapshot } = useLive()
  const hint = useHint()
  const merchant = useMerchant(merchantId)
  const conversation = useConversation(merchantId)
  const channel = useChannel(merchantId)
  const doctorLinks = useDoctorLinks()
  const { actions, busy, error, clearError } = useActions(merchantId, conversation.reload)
  const status = conversation.loaded.error && conversation.messages.length === 0 ? (
    <ErrorState error={conversation.loaded.error} title="Could not load the conversation" onRetry={conversation.reload} />
  ) : conversation.loaded.loading && conversation.messages.length === 0 ? (
    <Loading label="Loading chat…" />
  ) : null
  const announcement = latestSoundbox(conversation.messages)
  const footer = (
    <>
      {/* On narrow screens the Soundbox card sits far below the phone, so its line shows here too. */}
      {announcement ? (
        <div className="phone__soundbox">
          <SoundboxStrip message={announcement} pulse={conversation.pulse} />
        </div>
      ) : null}
      {error ? <InlineError error={error} onDismiss={clearError} /> : null}
      <Composer scenario={snapshot?.clock.scenario ?? null} busy={busy} actions={actions} hint={hint} />
    </>
  )
  const soundbox = <SoundboxDevice message={announcement} announcing={conversation.pulse} />
  return (
    <div className={isFeatureEnabled('n1_miniapp') ? 'merchant-page merchant-page--app' : 'merchant-page'}>
      <Phone now={snapshot?.clock.now ?? ''} messages={chatMessages(conversation.messages)} status={status} footer={footer} channel={channel.preferred} />
      <Feature name="n1_miniapp">
        <Suspense
          fallback={
            <div className="phone phone--app" aria-busy="true">
              <Loading label="Loading the app…" />
            </div>
          }
        >
          <AppFrame merchantId={merchantId} />
        </Suspense>
      </Feature>
      {merchant.data ? (
        <MerchantPanel
          merchant={merchant.data}
          scenario={snapshot?.clock.scenario ?? null}
          soundbox={soundbox}
          offer={coverOffer(conversation.messages)}
          steps={happenedSteps(merchant.data, conversation.messages)}
          channel={
            <>
              <ChannelSwitch state={channel} />
              <DoctorLinkCard state={doctorLinks} />
            </>
          }
        />
      ) : merchant.error ? (
        <ErrorState error={merchant.error} title="Could not load the merchant" onRetry={merchant.reload} />
      ) : (
        <Loading label="Loading merchant…" />
      )}
    </div>
  )
}

export default function Merchant() {
  const params = useParams()
  const merchantId = validId(params.id)
  if (!merchantId) {
    return <ErrorState error={new ApiError('VALIDATION_ERROR', 'Merchant ids look like S-0142', 0)} title="Unknown merchant" />
  }
  return <MerchantView key={merchantId} merchantId={merchantId} />
}
