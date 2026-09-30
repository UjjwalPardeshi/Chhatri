/**
 * WhatsApp bubbles (SPEC §13.1, §20 "Merchant phone", deck slides 1 and 7): Hindi line + English
 * line, payout card with badge, case chip, voice note (waveform that fills while it plays, with
 * its duration; a compact grey one beside Chhatri's spoken lines), slip photo, and the Paytm premium link drawn as a payment card (§13.4 COVER_LINK).
 */
import { useState } from 'react'
import { Link } from 'react-router'

import type { Message } from '../../api/types'
import { clipDuration, hhmm } from '../../lib/time'
import { useLive } from '../../state/live'
import { Icon } from '../common/Icon'
import { coverLink } from './coverOffer'
import { linkify } from './linkify'
import { spokenText, voiceAudioUrl, voiceSeconds, voiceSourceLabel, type VoiceSourceLabel } from './messages'
import { PaytmLinkCard } from './PaytmLinkCard'
import { Waveform } from './Waveform'

function Stamp({ message }: { message: Message }) {
  const mine = message.direction === 'INBOUND'
  return (
    <span className="bubble__stamp num">
      {hhmm(message.created_at)}
      {mine ? <span className="bubble__ticks" aria-label="read">✓✓</span> : null}
    </span>
  )
}

/** "0:05 · browser voice" beside an outgoing message's play button (SPEC §20 "Sound": labelled). */
export function voiceNote(message: Message): string {
  return `${clipDuration(voiceSeconds(message))} · ${voiceSourceLabel(message)}`
}

const PLAY_TITLES: Readonly<Record<VoiceSourceLabel, string>> = Object.freeze({
  'Sarvam voice': 'Play Sarvam Bulbul audio',
  recording: 'Play the recording',
  'browser voice': 'Play with the browser voice (hi-IN), simulated',
})

const VOICE_TAGS: Readonly<Record<VoiceSourceLabel, string>> = Object.freeze({
  'Sarvam voice': 'Sarvam voice',
  recording: 'recorded voice note',
  'browser voice': 'browser voice · simulated',
})

function PlayButton({ message, small = false, onPlay }: { message: Message; small?: boolean; onPlay?: () => void }) {
  const { sound } = useLive()
  const { text, lang } = spokenText(message)
  const source = voiceSourceLabel(message)
  return (
    <button
      type="button"
      className={`play-btn ${small ? 'play-btn--small' : ''}`}
      aria-label={`Play voice note (${source})`}
      title={PLAY_TITLES[source]}
      onClick={() => {
        onPlay?.()
        void sound.play(text, voiceAudioUrl(message), lang)
      }}
    >
      <Icon name="play" size={small ? 12 : 16} />
    </button>
  )
}

/** Play button, a small grey waveform and "0:05 · browser voice" under one of Chhatri's lines. */
function SpokenFoot({ message }: { message: Message }) {
  const [playKey, setPlayKey] = useState(0)
  return (
    <>
      <PlayButton message={message} small onPlay={() => setPlayKey((k) => k + 1)} />
      <Waveform seed={message.id} seconds={voiceSeconds(message)} playKey={playKey} compact />
      <span className="bubble__voice num">{voiceNote(message)}</span>
    </>
  )
}

function Lines({ message }: { message: Message }) {
  return (
    <>
      {message.text_hi ? (
        <p className="bubble__hi hi" lang="hi">
          {linkify(message.text_hi)}
        </p>
      ) : null}
      {message.text_en ? <p className={message.text_hi ? 'bubble__en' : 'bubble__only'}>{linkify(message.text_en)}</p> : null}
    </>
  )
}

function VoiceBubble({ message }: { message: Message }) {
  const source = voiceSourceLabel(message)
  const [playKey, setPlayKey] = useState(0)
  const seconds = voiceSeconds(message)
  return (
    <div className="voice">
      <div className="voice__row">
        <PlayButton message={message} onPlay={() => setPlayKey((k) => k + 1)} />
        <Waveform seed={message.id} seconds={seconds} playKey={playKey} />
        <span className="voice__time num">{clipDuration(seconds)}</span>
      </div>
      <Lines message={message} />
      <span className={`voice__tag ${source === 'Sarvam voice' ? 'voice__tag--live' : ''}`}>{VOICE_TAGS[source]}</span>
    </div>
  )
}

function PayoutCard({ message }: { message: Message }) {
  const card = message.card
  if (!card) return null
  return (
    <div className="payout-card">
      <div className="payout-card__head">
        <span>Paytm</span>
        <span className="payout-card__brand">Chhatri payout</span>
      </div>
      <div className="payout-card__body">
        <strong className="payout-card__amount num">{card.amount_label}</strong>
        <p className="payout-card__sub">
          <span className="hi" lang="hi">
            {card.subtitle_hi}
          </span>{' '}
          · {card.subtitle_en}
        </p>
        <span className="payout-card__badge">{card.badge}</span>
        {card.footer_en ? <p className="payout-card__footer">{card.footer_en}</p> : null}
        <Stamp message={message} />
      </div>
    </div>
  )
}

function ImageBubble({ message }: { message: Message }) {
  return (
    <figure className="photo">
      {message.media_url ? <img src={message.media_url} alt={message.text_en ?? 'Photo sent by the merchant'} loading="lazy" /> : null}
      <figcaption>{message.text_en ?? 'photo'}</figcaption>
    </figure>
  )
}

export function CaseChip({ message }: { message: Message }) {
  const caseId = message.meta.case_id
  const text = message.text_en ?? `Sent to a claims officer · case ${caseId ?? ''}`
  return (
    <div className="case-chip-row" data-at={message.created_at}>
      {caseId ? (
        <Link className="case-chip" to={`/claims?case=${encodeURIComponent(caseId)}`}>
          {text}
        </Link>
      ) : (
        <span className="case-chip">{text}</span>
      )}
    </div>
  )
}

export function MessageBubble({ message }: { message: Message }) {
  if (message.kind === 'CASE_CHIP') return <CaseChip message={message} />
  const mine = message.direction === 'INBOUND'
  const side = mine ? 'bubble--mine' : 'bubble--theirs'
  if (message.kind === 'PAYOUT_CARD') {
    return (
      <div className={`bubble-row ${side}`} data-kind={message.kind} data-at={message.created_at}>
        <PayoutCard message={message} />
      </div>
    )
  }
  const link = coverLink(message)
  if (link) {
    return (
      <div className={`bubble-row ${side}`} data-kind="PAYTM_LINK" data-at={message.created_at}>
        <PaytmLinkCard message={message} link={link} stamp={<Stamp message={message} />} />
      </div>
    )
  }
  const speakable = !mine && (message.text_hi || message.text_en) && message.kind !== 'VOICE'
  return (
    <div className={`bubble-row ${side}`} data-kind={message.kind} data-at={message.created_at}>
      <div className={`bubble ${side}`}>
        {message.kind === 'VOICE' ? <VoiceBubble message={message} /> : null}
        {message.kind === 'IMAGE' ? <ImageBubble message={message} /> : null}
        {message.kind !== 'VOICE' && message.kind !== 'IMAGE' ? <Lines message={message} /> : null}
        <div className="bubble__foot">
          {speakable ? <SpokenFoot message={message} /> : null}
          <Stamp message={message} />
        </div>
      </div>
    </div>
  )
}
