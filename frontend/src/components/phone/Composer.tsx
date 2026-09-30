/**
 * Phone composer (SPEC §20): quick chips for the demo utterances (voice or text, as in the deck),
 * a text box, mic recording (live STT when Sarvam is live) and photo upload + sample slips.
 */
import { useRef, useState, type FormEvent } from 'react'

import type { ScenarioName, VoiceDemoKey } from '../../api/types'
import { Icon } from '../common/Icon'
import { MAX_RECORD_SECONDS, useRecorder } from './useRecorder'

export type QuickChip = { id: string; hi: string | null; en: string; voice: VoiceDemoKey | null; scenarios: readonly ScenarioName[] }

export const QUICK_CHIPS: readonly QuickChip[] = [
  { id: 'why', hi: 'मुझे इतने ही पैसे क्यों मिले?', en: 'Why did I get only this much?', voice: 'why', scenarios: ['monsoon'] },
  { id: 'dispute', hi: 'मेरा नुकसान ज़्यादा हुआ।', en: 'My loss was bigger.', voice: null, scenarios: ['monsoon'] },
  { id: 'ill', hi: 'मैं अस्पताल में हूँ, बुखार है।', en: "I'm in hospital with a fever.", voice: 'ill', scenarios: ['illness', 'illness_mismatch'] },
  { id: 'cover', hi: null, en: 'Red alert tomorrow. Cover me today.', voice: null, scenarios: ['buy_cover'] },
]

export const SAMPLE_SLIPS: readonly { file: string; label: string }[] = [
  { file: 'anil_admission_slip.png', label: "Anil's admission slip" },
  { file: 'mismatch_admission_slip.png', label: 'Slip with a different name' },
  { file: 'blurry_slip.png', label: 'Blurry slip' },
]

export function orderedChips(scenario: ScenarioName | null): QuickChip[] {
  const relevant = QUICK_CHIPS.filter((c) => scenario !== null && c.scenarios.includes(scenario))
  return [...relevant, ...QUICK_CHIPS.filter((c) => !relevant.includes(c))]
}

export type ComposerActions = {
  sendText: (text: string) => Promise<boolean>
  sendVoiceDemo: (key: VoiceDemoKey) => Promise<boolean>
  sendVoice: (blob: Blob, filename: string) => Promise<boolean>
  sendPhoto: (file: File) => Promise<boolean>
  sendSample: (file: string) => Promise<boolean>
}

/** `hint`: the chip a launcher asked the presenter to tap next (highlighted until used). */
type Props = { scenario: ScenarioName | null; busy: boolean; actions: ComposerActions; hint?: string | null }

export function Composer({ scenario, busy, actions, hint = null }: Props) {
  const [used, setUsed] = useState<string | null>(null)
  const [text, setText] = useState('')
  const [slipsOpen, setSlipsOpen] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const recorder = useRecorder((blob, filename) => void actions.sendVoice(blob, filename))
  const relevant = new Set(orderedChips(scenario).filter((c) => scenario && c.scenarios.includes(scenario)).map((c) => c.id))

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (text.trim() === '') return
    if (await actions.sendText(text)) setText('')
  }
  const chip = (c: QuickChip) => {
    setUsed(c.id)
    void (c.voice ? actions.sendVoiceDemo(c.voice) : actions.sendText(c.hi ?? c.en))
  }
  const recording = recorder.state.status === 'recording'

  return (
    <div className="composer">
      <fieldset className="chips" aria-label="Demo replies">
        {orderedChips(scenario).map((c) => (
          <button key={c.id} type="button" className={`chip ${relevant.has(c.id) ? 'chip--hot' : ''} ${hint === c.id && used === null ? 'chip--hint' : ''}`} disabled={busy} title={c.en} onClick={() => chip(c)}>
            {c.voice ? <Icon name="mic" size={14} title="Sent as a voice note" /> : null}
            <span className={c.hi ? 'hi' : undefined} lang={c.hi ? 'hi' : undefined}>
              {c.hi ?? c.en}
            </span>
          </button>
        ))}
      </fieldset>
      {slipsOpen ? (
        <div className="slips" role="menu" aria-label="Sample slips">
          {SAMPLE_SLIPS.map((slip) => (
            <button key={slip.file} type="button" role="menuitem" className="slip" disabled={busy} onClick={() => { setSlipsOpen(false); void actions.sendSample(slip.file) }}>
              <img src={`/slips/${slip.file}`} alt="" />
              <span>{slip.label}</span>
            </button>
          ))}
          <button type="button" role="menuitem" className="slip slip--upload" disabled={busy} onClick={() => { setSlipsOpen(false); fileRef.current?.click() }}>
            <Icon name="camera" size={22} />
            <span>Upload a photo</span>
          </button>
        </div>
      ) : null}
      {recorder.state.error ? <p className="composer__error" role="alert">{recorder.state.error}</p> : null}
      <form className="composer__bar" onSubmit={(e) => void submit(e)}>
        <button type="button" className="round-btn round-btn--ghost" aria-label="Send a photo" aria-expanded={slipsOpen} onClick={() => setSlipsOpen((v) => !v)}>
          <Icon name="camera" size={18} />
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          hidden
          aria-label="Upload a photo"
          onChange={(e) => {
            const file = e.target.files?.[0]
            e.target.value = ''
            if (file) void actions.sendPhoto(file)
          }}
        />
        {recording ? (
          <output className="composer__recording">
            <span className="rec-dot" /> Recording 0:{String(recorder.state.seconds).padStart(2, '0')} / 0:{MAX_RECORD_SECONDS}
          </output>
        ) : (
          <input className="composer__input" value={text} placeholder="Message" aria-label="Message" disabled={busy} onChange={(e) => setText(e.target.value)} />
        )}
        {text.trim() !== '' && !recording ? (
          <button type="submit" className="round-btn" aria-label="Send" disabled={busy}>
            <Icon name="send" size={18} />
          </button>
        ) : (
          <button type="button" className={`round-btn ${recording ? 'round-btn--rec' : ''}`} aria-label={recording ? 'Stop and send voice note' : 'Record a voice note'} disabled={busy && !recording} onClick={() => (recording ? recorder.stop() : void recorder.start())}>
            <Icon name={recording ? 'stop' : 'mic'} size={18} />
          </button>
        )}
      </form>
    </div>
  )
}
