/**
 * The shop's Paytm Soundbox beside the phone (SPEC §13.4 SOUNDBOX, §19.1 `soundbox`, deck slides
 * 1 and 7): a small dark speaker whose LED ring lights up while it announces, with the Hindi line
 * it speaks and the English line under it. Always simulated (SPEC §0.1), and labelled so.
 */
import type { Message } from '../../api/types'
import { hhmm } from '../../lib/time'

type Props = { message: Message | null; announcing: boolean }

export function SoundboxDevice({ message, announcing }: Props) {
  return (
    <section className={`card soundbox-device ${announcing ? 'is-announcing' : ''}`} aria-label="Soundbox" aria-live="polite" data-idle={message === null}>
      <span className="soundbox-device__speaker" aria-hidden="true">
        <span className="soundbox-device__ring" />
        <span className="soundbox-device__grille" />
        <span className="soundbox-device__brand">Chhatri</span>
      </span>
      <div className="soundbox-device__text">
        <p className="eyebrow">
          Soundbox <span className="soundbox-device__sim">· simulated</span>
        </p>
        {message ? (
          <>
            <p className="soundbox-device__hi">“{message.text_hi}”</p>
            {message.text_en ? <p className="soundbox-device__en">“{message.text_en}”</p> : null}
            <p className="soundbox-device__at muted num">Announced {hhmm(message.created_at)}</p>
          </>
        ) : (
          <p className="muted">Waiting for a payment</p>
        )}
      </div>
    </section>
  )
}
