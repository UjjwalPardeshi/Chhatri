/**
 * The Telegram channel routes in the mock (data-model-and-api 5.13, flag telegram_channel). The merchant's chat app lives
 * in the runtime, so a load starts again on WhatsApp; both channels are SIMULATED, no chat is linked and no bot is known
 * (so no deep link). POST needs the officer token and audits `channel.preference_set` once per change. Outbound messages
 * of a merchant on Telegram carry channel TELEGRAM (MockRuntime.send).
 */
import type { ChannelView, PreferredChannel } from '../api/types'
import { isFeatureEnabled } from '../features'
import { bodyField, invalid, merchantParam, notFound, ok, requireOfficer, type Handler, type Route } from './http'
import type { MockRuntime } from './runtime'

const OFFICER_ACTOR = 'officer:officer'

function gate(): void {
  if (!isFeatureEnabled('telegram_channel')) throw notFound('route')
}

export function channelView(rt: MockRuntime, merchantId: string): ChannelView {
  return {
    merchant_id: merchantId,
    preferred_channel: rt.preferred.get(merchantId) ?? 'whatsapp',
    channels: [
      { channel: 'whatsapp', mode: 'SIMULATED' },
      { channel: 'telegram', mode: 'SIMULATED', linked: false, bot_username: null, deep_link: null },
    ],
  }
}

const getChannel: Handler = (ctx) => {
  gate()
  return ok(channelView(ctx.backend.runtime, merchantParam(ctx).id))
}

const setChannel: Handler = (ctx) => {
  gate()
  requireOfficer(ctx)
  const merchant = merchantParam(ctx)
  const channel = bodyField(ctx.body, 'channel')
  if (channel !== 'whatsapp' && channel !== 'telegram') throw invalid('channel', 'whatsapp or telegram')
  const rt = ctx.backend.runtime
  const chosen: PreferredChannel = channel
  if ((rt.preferred.get(merchant.id) ?? 'whatsapp') !== chosen) {
    rt.preferred.set(merchant.id, chosen)
    rt.record(OFFICER_ACTOR, 'channel.preference_set', 'merchant', merchant.id, { merchant_id: merchant.id, channel: chosen })
  }
  return ok(channelView(rt, merchant.id))
}

export const CHANNEL_ROUTES: readonly Route[] = [
  { method: 'GET', pattern: /^\/api\/merchants\/(S-\d{4})\/channel$/, handler: getChannel },
  { method: 'POST', pattern: /^\/api\/merchants\/(S-\d{4})\/channel$/, handler: setChannel },
]
