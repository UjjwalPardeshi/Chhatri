/**
 * The chat app switch beside the merchant phone (flag telegram_channel): WhatsApp or Telegram for this merchant's
 * messages, the mode of each (LIVE, SIMULATED or FALLBACK) and, for Telegram, whether a chat is linked with the bot's
 * deep link ("Open @chaatri_paytm_bot"). Payouts never depend on it.
 */
import type { PreferredChannel } from '../../api/types'
import type { ChannelState } from '../../state/useChannel'
import { InlineError } from '../common/Status'

const OPTIONS: readonly { id: PreferredChannel; label: string }[] = [
  { id: 'whatsapp', label: 'WhatsApp' },
  { id: 'telegram', label: 'Telegram' },
]

/** "Telegram · LIVE · chat linked" for the line under the switch. */
export function channelLine(state: Pick<ChannelState, 'view' | 'telegram' | 'preferred'>): string {
  const mode = state.view?.channels.find((c) => c.channel === state.preferred)?.mode ?? 'SIMULATED'
  if (state.preferred === 'whatsapp') return `WhatsApp · ${mode}`
  const linked = state.telegram?.linked ? 'chat linked' : 'no chat linked yet'
  return `Telegram · ${mode} · ${linked}`
}

export function ChannelSwitch({ state }: { state: ChannelState }) {
  if (!state.on) return null
  const telegram = state.telegram
  return (
    <section className="card merchant-card channel-card" aria-label="Chat app">
      <div className="channel-card__head">
        <h2>Chat app</h2>
        <fieldset className="channel-switch" aria-label="Where Chhatri's messages go">
          {OPTIONS.map((option) => (
            <button
              key={option.id}
              type="button"
              aria-pressed={state.preferred === option.id}
              className="channel-switch__option"
              data-channel={option.id}
              disabled={state.busy || state.view === null}
              onClick={() => (state.preferred === option.id ? undefined : void state.choose(option.id))}
            >
              {option.label}
            </button>
          ))}
        </fieldset>
      </div>
      <p className="channel-card__line" data-testid="channel-line">
        {channelLine(state)}
        {state.preferred === 'telegram' && telegram?.deep_link ? (
          <>
            {' · '}
            <a href={telegram.deep_link} target="_blank" rel="noreferrer">
              Open {telegram.bot_username ? `@${telegram.bot_username}` : 'the bot'}
            </a>
          </>
        ) : null}
      </p>
      <p className="channel-card__note">Only where messages go changes: cover and payouts stay the same.</p>
      {state.error ? <InlineError error={state.error} /> : null}
    </section>
  )
}
