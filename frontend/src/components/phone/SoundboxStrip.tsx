/** Soundbox strip (SPEC §13.4 SOUNDBOX, deck slide 7): the shop speaker's latest announcement. */
import type { Message } from '../../api/types'
import { Icon } from '../common/Icon'

export function SoundboxStrip({ message, pulse }: { message: Message | null; pulse: boolean }) {
  if (!message) {
    return (
      <div className="soundbox soundbox--idle" aria-label="Soundbox">
        <Icon name="speaker" size={14} /> Soundbox · waiting for a payment
      </div>
    )
  }
  return (
    <section className={`soundbox ${pulse ? 'soundbox--pulse' : ''}`} aria-label="Soundbox" aria-live="polite">
      <p>
        <Icon name="speaker" size={14} /> Soundbox: “{message.text_hi}”
      </p>
      {message.text_en ? <p className="soundbox__en">“{message.text_en}”</p> : null}
    </section>
  )
}
