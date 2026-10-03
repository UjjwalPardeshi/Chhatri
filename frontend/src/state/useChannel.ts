/**
 * The merchant's chat app (flag telegram_channel; data-model-and-api 5.13): where Chhatri's messages go (WhatsApp, the
 * default, or Telegram), each channel's mode and, for Telegram, whether a chat is linked and the bot's deep link.
 * `choose` sets it with the officer token, as the other demo writes do. A replay load starts again on WhatsApp.
 * Telegram only changes where messages go: never what a merchant is paid.
 */
import { useState } from 'react'

import type { ApiError } from '../api/client'
import type { ChannelView, PreferredChannel, TelegramOption } from '../api/types'
import { isFeatureEnabled } from '../features'
import { useLive } from './live'
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

export function useChannel(merchantId: string): ChannelState {
  const { api, snapshot } = useLive()
  const on = isFeatureEnabled('telegram_channel')
  const scenarioKey = `${snapshot?.clock.scenario}|${snapshot?.clock.start}`
  const [version, setVersion] = useState(0)
  const loaded = useAsync((signal) => (on ? api.channel(merchantId, signal) : Promise.resolve(null)), [api, merchantId, on, scenarioKey, version])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const choose = async (channel: PreferredChannel): Promise<void> => {
    setBusy(true)
    try {
      await api.setChannel(merchantId, channel)
      setError(null)
      setVersion((v) => v + 1)
    } catch (reason) {
      setError(toApiError(reason))
    } finally {
      setBusy(false)
    }
  }
  const view = loaded.data ?? null
  return { on, view, telegram: telegramOf(view), preferred: view?.preferred_channel ?? 'whatsapp', busy, error: error ?? loaded.error, choose }
}
