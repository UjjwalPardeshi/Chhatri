/** Phone composer (SPEC §20): chips, text, photo upload, sample slips and mic recording. */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { Composer, orderedChips, type ComposerActions } from './Composer'

function actions() {
  return {
    sendText: vi.fn<ComposerActions['sendText']>().mockResolvedValue(true),
    sendVoiceDemo: vi.fn<ComposerActions['sendVoiceDemo']>().mockResolvedValue(true),
    sendVoice: vi.fn<ComposerActions['sendVoice']>().mockResolvedValue(true),
    sendPhoto: vi.fn<ComposerActions['sendPhoto']>().mockResolvedValue(true),
    sendSample: vi.fn<ComposerActions['sendSample']>().mockResolvedValue(true),
  }
}

type Media = { getTracks: () => { stop: () => void }[] }

class FakeRecorder {
  static isTypeSupported = (type: string) => type === 'audio/ogg;codecs=opus'
  static last: FakeRecorder | null = null
  state = 'inactive'
  mimeType: string
  stream: { getTracks: () => { stop: () => void }[] }
  ondataavailable: ((e: { data: Blob }) => void) | null = null
  onstop: (() => void) | null = null
  constructor(stream: FakeRecorder['stream'], options?: { mimeType: string }) {
    this.stream = stream
    this.mimeType = options?.mimeType ?? ''
    FakeRecorder.last = this
  }
  start() {
    this.state = 'recording'
  }
  stop() {
    this.state = 'inactive'
    this.ondataavailable?.({ data: new Blob(['a']) })
    this.onstop?.()
  }
}

beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
})

describe('Composer', () => {
  it('orders chips for the scenario and sends voice demos or text', () => {
    expect(orderedChips('buy_cover')[0].id).toBe('cover')
    expect(orderedChips(null).map((c) => c.id)).toEqual(['why', 'dispute', 'ill', 'cover'])
    const a = actions()
    render(<Composer scenario="monsoon" busy={false} actions={a} />)
    fireEvent.click(screen.getByTitle('Why did I get only this much?'))
    expect(a.sendVoiceDemo).toHaveBeenCalledWith('why')
    fireEvent.click(screen.getByTitle('My loss was bigger.'))
    expect(a.sendText).toHaveBeenCalledWith('मेरा नुकसान ज़्यादा हुआ।')
    fireEvent.click(screen.getByTitle('Red alert tomorrow. Cover me today.'))
    expect(a.sendText).toHaveBeenCalledWith('Red alert tomorrow. Cover me today.')
  })

  it('ignores blank text, uploads photos and sends sample slips', () => {
    const a = actions()
    render(<Composer scenario="illness" busy={false} actions={a} />)
    fireEvent.submit(screen.getByRole('textbox', { name: 'Message' }).closest('form') as HTMLFormElement)
    expect(a.sendText).not.toHaveBeenCalled()
    const input = screen.getByLabelText('Upload a photo', { selector: 'input' }) as HTMLInputElement
    const file = new File(['x'], 'slip.png', { type: 'image/png' })
    fireEvent.change(input, { target: { files: [file] } })
    expect(a.sendPhoto).toHaveBeenCalledWith(file)
    fireEvent.change(input, { target: { files: [] } })
    expect(a.sendPhoto).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: 'Send a photo' }))
    fireEvent.click(screen.getByRole('menuitem', { name: /Blurry slip/ }))
    expect(a.sendSample).toHaveBeenCalledWith('blurry_slip.png')
    fireEvent.click(screen.getByRole('button', { name: 'Send a photo' }))
    const click = vi.spyOn(input, 'click').mockImplementation(() => undefined)
    fireEvent.click(screen.getByRole('menuitem', { name: /Upload a photo/ }))
    expect(click).toHaveBeenCalled()
  })

  it('records a voice note and sends it on stop', async () => {
    const stopTrack = vi.fn<() => void>()
    vi.stubGlobal('MediaRecorder', FakeRecorder)
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia: vi.fn<() => Promise<Media>>().mockResolvedValue({ getTracks: () => [{ stop: stopTrack }] }) } })
    const a = actions()
    render(<Composer scenario="illness" busy={false} actions={a} />)
    fireEvent.click(screen.getByRole('button', { name: 'Record a voice note' }))
    expect(await screen.findByText(/Recording 0:00/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Stop and send voice note' }))
    await waitFor(() => expect(a.sendVoice).toHaveBeenCalledWith(expect.any(Blob), 'voice-note.ogg'))
    expect(stopTrack).toHaveBeenCalled()
  })

  it('stops by itself at the 30-second limit', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('MediaRecorder', FakeRecorder)
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia: vi.fn<() => Promise<Media>>().mockResolvedValue({ getTracks: () => [] }) } })
    const a = actions()
    render(<Composer scenario="illness" busy={false} actions={a} />)
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Record a voice note' }))
    })
    await act(async () => {
      vi.advanceTimersByTime(30_000)
    })
    expect(a.sendVoice).toHaveBeenCalledTimes(1)
  })

  it('explains when the microphone is unavailable or denied', async () => {
    vi.stubGlobal('MediaRecorder', undefined)
    const { unmount } = render(<Composer scenario="illness" busy={false} actions={actions()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Record a voice note' }))
    expect(await screen.findByText('This browser cannot record audio')).toBeTruthy()
    unmount()
    vi.stubGlobal('MediaRecorder', FakeRecorder)
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia: vi.fn<() => Promise<Media>>().mockRejectedValue(new Error('denied')) } })
    render(<Composer scenario="illness" busy={false} actions={actions()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Record a voice note' }))
    expect(await screen.findByText('Microphone permission denied or unavailable')).toBeTruthy()
  })
})
