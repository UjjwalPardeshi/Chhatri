/** "Enable sound" (SPEC §20 "Sound"): one presenter click unlocks Soundbox and voice auto-play. */
import { useEffect, useState } from 'react'

import { useLive } from '../../state/live'
import { Icon } from '../common/Icon'

export function SoundToggle() {
  const { sound } = useLive()
  const [enabled, setEnabled] = useState(sound.isEnabled())
  useEffect(() => sound.subscribe(setEnabled), [sound])

  const toggle = () => {
    const next = !enabled
    sound.setEnabled(next)
    if (next) sound.speak(' ')
  }

  return (
    <button type="button" className={`sound-toggle ${enabled ? 'sound-toggle--on' : ''}`} aria-pressed={enabled} onClick={toggle}>
      <Icon name={enabled ? 'sound-on' : 'sound-off'} size={16} />
      <span className="sound-toggle__text">{enabled ? 'Sound on' : 'Enable sound'}</span>
    </button>
  )
}
