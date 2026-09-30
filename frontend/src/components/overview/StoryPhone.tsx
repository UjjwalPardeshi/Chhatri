/**
 * A deck conversation (slides 1 and 7) rendered by the real phone components, so the Overview shows
 * exactly what the merchant sees in the live demo (SPEC §13.4 strings, §20 "Merchant phone").
 */
import type { Message } from '../../api/types'
import { Phone } from '../phone/Phone'
import { SoundboxStrip } from '../phone/SoundboxStrip'

type Props = { now: string; thread: readonly Message[]; soundbox: Message | null; className?: string }

export function StoryPhone({ now, thread, soundbox, className = '' }: Props) {
  const footer = soundbox ? <SoundboxStrip message={soundbox} pulse={false} /> : null
  return (
    <div className={`story-phone ${className}`}>
      <Phone now={now} messages={thread} status={null} footer={footer} testId="story-phone" autoScroll={false} />
    </div>
  )
}
