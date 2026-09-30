/**
 * WhatsApp bubbles (SPEC §13.1, §20 "Merchant phone", deck slides 1 and 7): Hindi line + English
 * line, payout card with badge, case chip, voice note with play button and duration, slip photo.
 */
import { Link } from 'react-router'

import type { Message } from '../../api/types'
import { clipDuration, hhmm } from '../../lib/time'
import { useLive } from '../../state/live'
import { Icon } from '../common/Icon'
import { linkify } from './linkify'
import { spokenText, voiceSeconds } from './messages'

const WAVE = [4, 9, 6, 12, 8, 14, 7, 11, 5, 10, 13, 6, 9, 4]

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
  const source = message.audio_url ? 'Sarvam voice' : 'browser voice'
  return `${clipDuration(voiceSeconds(message))} · ${source}`
}

function PlayButton({ message, small = false }: { message: Message; small?: boolean }) {
  const { sound } = useLive()
  const { text, lang } = spokenText(message)
  const source = message.audio_url ? 'Sarvam voice' : 'browser voice'
  return (
    <button
      type="button"
      className={`play-btn ${small ? 'play-btn--small' : ''}`}
      aria-label={`Play voice note (${source})`}
      title={message.audio_url ? 'Play Sarvam Bulbul audio' : 'Play with the browser voice (hi-IN), simulated'}
      onClick={() => void sound.play(text, message.audio_url, lang)}
    >
      <Icon name="play" size={small ? 12 : 16} />
    </button>
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
  const browserVoice = !message.audio_url || message.meta.voice_source === 'browser-simulated'
  return (
    <div className="voice">
      <div className="voice__row">
        <PlayButton message={message} />
        <span className="voice__wave" aria-hidden="true">
          {WAVE.map((h, i) => (
            <span key={i} style={{ height: `${h}px` }} />
          ))}
        </span>
        <span className="voice__time num">{clipDuration(voiceSeconds(message))}</span>
      </div>
      <Lines message={message} />
      {browserVoice ? <span className="voice__tag">browser voice · simulated</span> : <span className="voice__tag voice__tag--live">Sarvam voice</span>}
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
    <div className="case-chip-row">
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
      <div className={`bubble-row ${side}`} data-kind={message.kind}>
        <PayoutCard message={message} />
      </div>
    )
  }
  const speakable = !mine && (message.text_hi || message.text_en) && message.kind !== 'VOICE'
  return (
    <div className={`bubble-row ${side}`} data-kind={message.kind}>
      <div className={`bubble ${side}`}>
        {message.kind === 'VOICE' ? <VoiceBubble message={message} /> : null}
        {message.kind === 'IMAGE' ? <ImageBubble message={message} /> : null}
        {message.kind !== 'VOICE' && message.kind !== 'IMAGE' ? <Lines message={message} /> : null}
        <div className="bubble__foot">
          {speakable ? (
            <>
              <PlayButton message={message} small />
              <span className="bubble__voice num">{voiceNote(message)}</span>
            </>
          ) : null}
          <Stamp message={message} />
        </div>
      </div>
    </div>
  )
}
