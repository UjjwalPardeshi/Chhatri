/**
 * The merchant's chat app (flag telegram_channel; data-model-and-api 5.13): where Chhatri's messages go (WhatsApp, the
 * default, or Telegram), each channel's mode and, for Telegram, whether a chat is linked and the bot's deep link.
 * `choose` sets it with the officer token, as the other demo writes do, and shows the POST's own answer at once.
 * The view is read again on every scenario event (a load or reset may move the merchant back to WhatsApp, or keep a
 * linked Telegram chat, D3) and on the audit events that change it (`channel.preference_set`, `telegram.bound`,
 * `telegram.unbound`), so the switch always shows what the backend holds. Telegram only changes where messages go:
 * never what a merchant is paid.
 */
import { useRef, useState } from 'react'

import type { ApiError } from '../api/client'
import type { ChannelView, PreferredChannel, TelegramOption } from '../api/types'
import { isFeatureEnabled } from '../features'
import { useLive, useLiveEvent } from './live'
import { toApiError, useAsync } from './useAsync'

export type ChannelState = {
  on: boolean
  view: ChannelView | null
  telegram: TelegramOption | null
  preferred: PreferredChannel
  busy: boolean
  error: ApiError | null
  choose: (channel: PreferredChannel) => Promise<void>
}

export function telegramOf(view: ChannelView | null): TelegramOption | null {
  const option = view?.channels.find((c) => c.channel === 'telegram')
  return option && option.channel === 'telegram' ? option : null
}

/** The audit actions after which the chat app is read again. */
export const CHANNEL_AUDIT_ACTIONS: ReadonlySet<string> = new Set(['channel.preference_set', 'telegram.bound', 'telegram.unbound'])

export function useChannel(merchantId: string): ChannelState {
  const { api, snapshot } = useLive()
  const on = isFeatureEnabled('telegram_channel')
  const scenarioKey = `${snapshot?.clock.scenario}|${snapshot?.clock.start}`
  const [version, setVersion] = useState(0)
  /** Reads started so far: a read shows only if it started after the last POST was sent (an older one is stale). */
  const reads = useRef(0)
  const loaded = useAsync(
    (signal) => {
      if (!on) return Promise.resolve(null)
      const seq = ++reads.current
      return api.channel(merchantId, signal).then((view) => ({ seq, view }))
    },
    [api, merchantId, on, scenarioKey, version],
  )
  /** The POST's answer, shown until a read that started after the POST was sent lands. */
  const [posted, setPosted] = useState<{ after: number; view: ChannelView } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  useLiveEvent(['scenario', 'audit'], (event) => {
    if (!on) return
    if (event.type === 'scenario' || (event.type === 'audit' && CHANNEL_AUDIT_ACTIONS.has(event.data.action))) setVersion((v) => v + 1)
  })
  const base = loaded.data?.view ?? null
  const baseSeq = loaded.data?.seq ?? 0
  const choose = async (channel: PreferredChannel): Promise<void> => {
    setBusy(true)
    const sentAfter = reads.current
    try {
      const answer = await api.setChannel(merchantId, channel)
      setPosted({ after: sentAfter, view: answer })
      setError(null)
    } catch (reason) {
      setError(toApiError(reason))
    } finally {
      setBusy(false)
    }
  }
  const view = posted !== null && baseSeq <= posted.after ? posted.view : base
  return { on, view, telegram: telegramOf(view), preferred: view?.preferred_channel ?? 'whatsapp', busy, error: error ?? loaded.error, choose }
}
