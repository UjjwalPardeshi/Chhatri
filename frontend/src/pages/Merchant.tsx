/**
 * Merchant phone page (SPEC §13, §20 "Merchant phone"): the WhatsApp-like conversation for one
 * merchant, updated live from `message` events, with the merchant's money beside it.
 */
import { useCallback, useMemo, useState } from 'react'
import { useParams } from 'react-router'

import { assertMerchantId } from '../api/endpoints'
import type { Message, VoiceDemoKey } from '../api/types'
import { ErrorState, InlineError, Loading } from '../components/common/Status'
import { Composer, type ComposerActions } from '../components/phone/Composer'
import { MerchantPanel } from '../components/phone/MerchantPanel'
import { chatMessages, latestSoundbox, upsertMessage } from '../components/phone/messages'
import { Phone } from '../components/phone/Phone'
import { SoundboxStrip } from '../components/phone/SoundboxStrip'
import { ApiError } from '../api/client'
import { useLive, useLiveEvent } from '../state/live'
import { toApiError, useAsync } from '../state/useAsync'
import { useMerchant } from '../state/useMerchant'

const PULSE_MS = 2_400

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
    if (message.direction === 'OUTBOUND' && message.channel !== 'SOUNDBOX' && message.text_hi) void sound.autoPlay(message.text_hi, message.audio_url)
  })
  const reload = useCallback(() => setVersion((v) => v + 1), [])
  return { messages, loaded, pulse, reload }
}

function useActions(merchantId: string, reload: () => void) {
  const { api } = useLive()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const run = async (action: () => Promise<unknown>): Promise<boolean> => {
    setBusy(true)
    try {
      await action()
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
    sendPhoto: (file) => run(() => api.sendPhoto(merchantId, file)),
    sendSample: (file) => run(() => api.sendSampleSlip(merchantId, file)),
  }
  return { actions, busy, error, clearError: () => setError(null) }
}

function MerchantView({ merchantId }: { merchantId: string }) {
  const { snapshot } = useLive()
  const merchant = useMerchant(merchantId)
  const conversation = useConversation(merchantId)
  const { actions, busy, error, clearError } = useActions(merchantId, conversation.reload)
  const status = conversation.loaded.error && conversation.messages.length === 0 ? (
    <ErrorState error={conversation.loaded.error} title="Could not load the conversation" onRetry={conversation.reload} />
  ) : conversation.loaded.loading && conversation.messages.length === 0 ? (
    <Loading label="Loading chat…" />
  ) : null
  const footer = (
    <>
      <SoundboxStrip message={latestSoundbox(conversation.messages)} pulse={conversation.pulse} />
      {error ? <InlineError error={error} onDismiss={clearError} /> : null}
      <Composer scenario={snapshot?.clock.scenario ?? null} busy={busy} actions={actions} />
    </>
  )
  return (
    <div className="merchant-page">
      <Phone now={snapshot?.clock.now ?? ''} messages={chatMessages(conversation.messages)} status={status} footer={footer} />
      {merchant.data ? (
        <MerchantPanel merchant={merchant.data} scenario={snapshot?.clock.scenario ?? null} />
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
