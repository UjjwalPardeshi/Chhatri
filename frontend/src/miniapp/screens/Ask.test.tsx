/** Ask Chhatri (N2) and voice (N4): the screen, its states, the answer parts, the scam banner, and the mic with its chips. */
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import type { MockBackend } from '../../mock/backend'
import { testApi } from '../../mock/testkit'
import { NOTICE_STORAGE_KEY } from '../components/voiceQuestion'
import { renderStandalone } from '../shell/shellKit'

let backend: MockBackend
type Listener = (event: Event & { results?: { transcript: string }[][]; error?: string }) => void

/** The browser's SpeechRecognition as far as the voice engine uses it: listeners, start, stop and abort. */
class FakeRecognition {
  static last: FakeRecognition | null = null
  lang = ''
  continuous = false
  interimResults = false
  private readonly listeners = new Map<string, Listener[]>()
  addEventListener(type: string, listener: Listener): void {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener])
  }
  private emit(type: string, extra: object = {}): void {
    for (const listener of this.listeners.get(type) ?? []) listener(Object.assign(new Event(type), extra))
  }
  start(): void {
    FakeRecognition.last = this
  }
  stop(): void {
    this.emit('end')
  }
  abort(): void {}
  say(words: string): void {
    this.emit('result', { results: [[{ transcript: words }]] })
  }
  fail(error: string): void {
    this.emit('error', { error })
  }
}

/** The browser's utterance: listeners are kept so the test can say it has finished. */
class FakeUtterance extends EventTarget {
  lang = ''
  readonly text: string
  constructor(text: string) {
    super()
    this.text = text
  }
}

async function speakOnce(words: string) {
  win.SpeechRecognition = FakeRecognition
  const api = await openAsk()
  fireEvent.click(screen.getByTestId('voice-mic'))
  await waitFor(() => expect(screen.getByTestId('voice-status').getAttribute('data-phase')).toBe('listening'))
  act(() => FakeRecognition.last?.say(words))
  fireEvent.click(screen.getByTestId('voice-mic'))
  return api
}

const win = window as unknown as Record<string, unknown>

beforeEach(() => {
  vi.stubEnv('VITE_FEATURES', 'n2_ask_chhatri,n4_voice')
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  window.localStorage.clear()
  window.localStorage.setItem(NOTICE_STORAGE_KEY, '1')
  FakeRecognition.last = null
})
afterEach(() => {
  backend?.dispose()
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
  delete win.SpeechRecognition
  delete win.speechSynthesis
  delete win.SpeechSynthesisUtterance
})

async function openAsk(search = '?lang=en&screen=ask') {
  const kit = testApi()
  backend = kit.backend
  await kit.api.seek('17:05')
  renderStandalone(`/merchant/S-0142/app${search}`, kit.backend, kit.api)
  await waitFor(() => expect(screen.getByTestId('screen-ask').getAttribute('data-state')).not.toBe('loading'))
  return kit.api
}

const type = (value: string) => fireEvent.change(screen.getByTestId('ask-input'), { target: { value } })
const send = () => fireEvent.click(screen.getByTestId('ask-send'))
const textOf = (id: string) => screen.getByTestId(id).textContent ?? ''

describe('Ask Chhatri: the flag', () => {
  it('shows Home for screen=ask and no Help row while n2_ask_chhatri is off', async () => {
    vi.stubEnv('VITE_FEATURES', '')
    const kit = testApi()
    backend = kit.backend
    renderStandalone('/merchant/S-0142/app?lang=en&screen=ask', kit.backend, kit.api)
    expect(await screen.findByTestId('screen-home')).toBeTruthy()
    expect(screen.queryByTestId('screen-ask')).toBeNull()
  })

  it('opens from the Help row', async () => {
    const kit = testApi()
    backend = kit.backend
    renderStandalone('/merchant/S-0142/app?lang=en&screen=help', kit.backend, kit.api)
    fireEvent.click(await screen.findByTestId('help-ask'))
    expect(await screen.findByTestId('screen-ask')).toBeTruthy()
  })
})

describe('Ask Chhatri: the empty state', () => {
  it('says what can be asked, that the rules decide, and offers at most four ready questions', async () => {
    await openAsk()
    expect(screen.getByTestId('screen-ask').getAttribute('data-state')).toBe('empty')
    expect(textOf('ask-empty')).toContain('You can ask about your cover, your claims and your payouts.')
    expect(textOf('ask-empty')).toContain('The rules decide every payout, not this assistant.')
    const chips = screen.getAllByTestId('ask-suggest')
    expect(chips.length).toBeLessThanOrEqual(4)
    expect(chips[0].textContent).toBe('Why did I get this amount?')
  })

  it('reads in Hindi', async () => {
    await openAsk('?lang=hi&screen=ask')
    expect(textOf('ask-empty')).toContain('आप अपने कवर, दावों और भुगतानों के बारे में पूछ सकते हैं।')
    expect(screen.getByTestId('ask-input').getAttribute('placeholder')).toContain('अपने कवर, दावे या भुगतान')
  })
})

describe('Ask Chhatri: an answer', () => {
  it('shows the answer, clause chips, the facts with sources, the next step and the label', async () => {
    await openAsk()
    fireEvent.click(screen.getAllByTestId('ask-suggest')[0])
    const answer = await screen.findByTestId('ask-answer')
    expect(answer.getAttribute('data-mode')).toBe('SIMULATED')
    expect(within(answer).getByTestId('ask-answer-text').textContent).toContain('₹')
    expect(within(answer).getByTestId('ask-clauses').textContent).toContain('From the policy:')
    expect(within(answer).getByTestId('ask-clause').getAttribute('data-clause')).toBe('C4.1')
    expect(within(answer).getAllByTestId('source-badge').length).toBeGreaterThan(0)
    expect(within(answer).queryByTestId('source-missing')).toBeNull()
    expect(within(answer).getByTestId('ask-mode').textContent).toBe('SIMULATED')
    expect(within(answer).getByTestId('ask-provider').textContent).toBe('mock')
    expect(within(answer).getByTestId('ask-next').textContent).toBe('See my claim')
    expect(textOf('ask-question')).toBe('You: Why did I get this amount?')
  })

  it('opens the clause sheet and the Details sheet with the reason a backup was used', async () => {
    await openAsk()
    fireEvent.click(screen.getAllByTestId('ask-suggest')[0])
    fireEvent.click(await screen.findByTestId('ask-clause'))
    expect(await screen.findByTestId('ask-clause-sheet')).toBeTruthy()
    fireEvent.click(screen.getByTestId('ask-clause-close'))
    await waitFor(() => expect(screen.queryByTestId('ask-clause-sheet')).toBeNull())
    fireEvent.click(screen.getByTestId('ask-details-AQ-000001'))
    const sheet = await screen.findByTestId('ask-details-sheet')
    expect(within(sheet).getByTestId('ask-details-provider').textContent).toBe('mock')
    expect(within(sheet).queryByTestId('ask-details-model')).toBeNull()
    expect(within(sheet).getByTestId('ask-details-reason').textContent).toContain('This is the static demo, so recorded samples are shown.')
  })

  it('goes where the next step says', async () => {
    await openAsk()
    fireEvent.click(screen.getAllByTestId('ask-suggest')[0])
    fireEvent.click(await screen.findByTestId('ask-next'))
    expect(await screen.findByTestId('screen-claims')).toBeTruthy()
  })

  it('clears the box after an answer and sends typed text', async () => {
    await openAsk()
    type('What is the waiting period?')
    send()
    await screen.findByTestId('ask-answer')
    expect((screen.getByTestId('ask-input') as HTMLTextAreaElement).value).toBe('')
    expect(textOf('ask-answer-text')).toContain('7 days')
  })

  it('hands an unknown question to the team with the hand-off line', async () => {
    await openAsk()
    type('Can you buy me a car?')
    send()
    await screen.findByTestId('ask-answer-text')
    expect(textOf('ask-answer-text')).toContain("I don't have an answer to this question.")
    expect(screen.getByTestId('ask-next').textContent).toBe('Talk to the team')
  })
})

describe('Ask Chhatri: the scam warning', () => {
  it('shows an alert above the answer and still answers, with Ask another question as the step', async () => {
    await openAsk()
    type('Someone asked for my OTP to pay my claim')
    send()
    const banner = await screen.findByTestId('ask-scam')
    const alert = within(banner).getByRole('alert')
    expect(alert.textContent).toContain('Be careful. This looks like a scam.')
    expect(alert.textContent).toContain('does not ask for your OTP, PIN or password')
    expect(alert.textContent).toContain('This is a quick check of the words in the message. It can be wrong.')
    expect(within(banner).queryByText(/helpline/i)).toBeNull()
    const next = screen.getByTestId('ask-next')
    expect(next.textContent).toBe('Ask another question')
    fireEvent.click(next)
    expect(document.activeElement).toBe(screen.getByTestId('ask-input'))
  })
})

describe('Ask Chhatri: states', () => {
  it('shows thinking with Cancel, and Cancel drops the question', async () => {
    const api = await openAsk()
    vi.spyOn(api, 'ask').mockReturnValue(new Promise(() => undefined))
    type('hello')
    send()
    expect(await screen.findByTestId('ask-thinking')).toBeTruthy()
    expect(textOf('ask-thinking')).toContain('Looking at your records…')
    fireEvent.click(screen.getByTestId('ask-cancel'))
    await waitFor(() => expect(screen.queryByTestId('ask-entry')).toBeNull())
  })

  it('keeps the typed text after a failure and retries the same question', async () => {
    const api = await openAsk()
    const ask = vi.spyOn(api, 'ask').mockRejectedValueOnce(new ApiError('internal', 'boom', 500))
    type('hello')
    send()
    const failed = await screen.findByTestId('ask-failed')
    expect(failed.textContent).toContain('Something went wrong. Try again.')
    expect(failed.textContent).toContain('Error code: internal')
    expect((screen.getByTestId('ask-input') as HTMLTextAreaElement).value).toBe('hello')
    ask.mockRestore()
    fireEvent.click(screen.getByTestId('ask-retry'))
    await screen.findByTestId('ask-answer')
  })

  it('says there is a connection problem when the network fails', async () => {
    const api = await openAsk()
    vi.spyOn(api, 'ask').mockRejectedValueOnce(new ApiError('NETWORK_ERROR', 'down', 0))
    type('hello')
    send()
    expect((await screen.findByTestId('ask-failed')).textContent).toContain('There is a connection problem.')
  })

  it('shows ASK_OFFLINE, keeps the text, and turns Send and the mic off while offline', async () => {
    await openAsk()
    win.SpeechRecognition = FakeRecognition
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)
    act(() => {
      window.dispatchEvent(new Event('offline'))
    })
    type('hello')
    expect(await screen.findByTestId('ask-offline')).toBeTruthy()
    expect(screen.getByTestId('screen-ask').getAttribute('data-state')).toBe('offline')
    expect((screen.getByTestId('ask-send') as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByTestId('ask-input') as HTMLTextAreaElement).value).toBe('hello')
  })

  it('refuses a question over 500 characters with ASK_TOO_LONG', async () => {
    await openAsk()
    type('a'.repeat(501))
    expect(textOf('ask-counter')).toContain('Please keep the question shorter.')
    expect((screen.getByTestId('ask-send') as HTMLButtonElement).disabled).toBe(true)
  })

  it('has Send off for an empty box', async () => {
    await openAsk()
    expect((screen.getByTestId('ask-send') as HTMLButtonElement).disabled).toBe(true)
  })
})

describe('Voice (N4)', () => {
  it('has no mic and says voice is not available when the browser cannot listen', async () => {
    await openAsk()
    expect(screen.queryByTestId('voice-mic')).toBeNull()
    expect(textOf('voice-unavailable')).toContain('Voice is not available right now.')
  })

  it('has no voice parts while n4_voice is off', async () => {
    vi.stubEnv('VITE_FEATURES', 'n2_ask_chhatri')
    win.SpeechRecognition = FakeRecognition
    await openAsk()
    expect(screen.queryByTestId('voice-mic')).toBeNull()
    expect(screen.queryByTestId('voice-unavailable')).toBeNull()
  })

  it('shows the notice once before the first recording', async () => {
    window.localStorage.clear()
    win.SpeechRecognition = FakeRecognition
    await openAsk()
    fireEvent.click(screen.getByTestId('voice-mic'))
    expect(textOf('voice-notice')).toContain('Your voice may be sent to a speech service')
    fireEvent.click(screen.getByTestId('voice-notice-continue'))
    await waitFor(() => expect(screen.getByTestId('voice-status').getAttribute('data-phase')).toBe('listening'))
    expect(window.localStorage.getItem(NOTICE_STORAGE_KEY)).toBe('1')
  })

  it('listens with a timer, then fills the box and asks for each amount to be confirmed before Send works', async () => {
    const api = await speakOnce('डेढ़ हज़ार रुपये कब मिलेंगे')
    expect((await screen.findByTestId('voice-chip-m1')).textContent).toContain('₹1,500 — is that right?')
    expect((screen.getByTestId('ask-input') as HTMLTextAreaElement).value).toBe('डेढ़ हज़ार रुपये कब मिलेंगे')
    expect(textOf('ask-send-hint')).toBe('Confirm each amount and date to send.')
    expect((screen.getByTestId('ask-send') as HTMLButtonElement).disabled).toBe(true)
    const ask = vi.spyOn(api, 'ask')
    fireEvent.click(screen.getByTestId('voice-chip-right-m1'))
    expect(screen.getByTestId('voice-chip-m1').getAttribute('data-state')).toBe('confirmed')
    await waitFor(() => expect((screen.getByTestId('ask-send') as HTMLButtonElement).disabled).toBe(false))
    send()
    await screen.findByTestId('ask-answer')
    expect(ask).toHaveBeenCalledWith('S-0142', expect.objectContaining({ stt_id: 'ST-000001', confirmed_mentions: ['m1'], lang: 'en' }))
    expect(screen.queryByTestId('voice-confirm')).toBeNull()
  })

  it('gives an amount added by hand its own chip and holds Send until it is confirmed', async () => {
    await speakOnce('डेढ़ हज़ार रुपये कब मिलेंगे')
    fireEvent.click(await screen.findByTestId('voice-chip-right-m1'))
    type('डेढ़ हज़ार रुपये और 2000 रुपये')
    expect(await screen.findByTestId('voice-chip-m2')).toBeTruthy()
    expect(screen.getByTestId('voice-chip-m1').getAttribute('data-state')).toBe('confirmed')
    expect(screen.getByTestId('voice-chip-m2').getAttribute('data-state')).toBe('pending')
    expect((screen.getByTestId('ask-send') as HTMLButtonElement).disabled).toBe(true)
  })

  it('asks which day कल means and never guesses', async () => {
    await speakOnce('कल पैसे मिले')
    const chip = await screen.findByTestId('voice-chip-m1')
    expect(chip.textContent).toContain('Did you mean yesterday or tomorrow?')
    expect((screen.getByTestId('ask-send') as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(screen.getByTestId('voice-chip-kal-yesterday-m1'))
    await waitFor(() => expect((screen.getByTestId('ask-send') as HTMLButtonElement).disabled).toBe(false))
  })

  it('asks for the number to be typed when the words cannot be read', async () => {
    await speakOnce('डेढ़ रुपये चाहिए')
    expect((await screen.findByTestId('voice-chip-m1')).textContent).toContain('Please type the number.')
    expect(screen.queryByTestId('voice-chip-right-m1')).toBeNull()
    expect((screen.getByTestId('ask-send') as HTMLButtonElement).disabled).toBe(true)
  })

  it('sends at once when the words hold no amount or date', async () => {
    await speakOnce('मेरा कवर कब शुरू होता है')
    await waitFor(() => expect((screen.getByTestId('ask-input') as HTMLTextAreaElement).value).toContain('कवर'))
    expect(screen.queryByTestId('voice-confirm')).toBeNull()
    expect((screen.getByTestId('ask-send') as HTMLButtonElement).disabled).toBe(false)
  })

  it('says it heard nothing when the browser returns no words', async () => {
    win.SpeechRecognition = FakeRecognition
    await openAsk()
    fireEvent.click(screen.getByTestId('voice-mic'))
    await waitFor(() => expect(screen.getByTestId('voice-status').getAttribute('data-phase')).toBe('listening'))
    fireEvent.click(screen.getByTestId('voice-mic'))
    await waitFor(() => expect(textOf('voice-status')).toContain("Sorry, I couldn't hear that clearly."))
  })

  it('shows the way out when the microphone is refused', async () => {
    win.SpeechRecognition = FakeRecognition
    await openAsk()
    fireEvent.click(screen.getByTestId('voice-mic'))
    await waitFor(() => expect(FakeRecognition.last).not.toBeNull())
    act(() => FakeRecognition.last?.fail('not-allowed'))
    await waitFor(() => expect(textOf('voice-status')).toContain('Microphone permission denied or unavailable'))
    expect(textOf('voice-status')).toContain('or type your message instead.')
  })

  it('stops itself at 30 seconds', async () => {
    win.SpeechRecognition = FakeRecognition
    await openAsk()
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      fireEvent.click(screen.getByTestId('voice-mic'))
      await waitFor(() => expect(screen.getByTestId('voice-status').getAttribute('data-phase')).toBe('listening'))
      act(() => FakeRecognition.last?.say('मेरा कवर कब शुरू होता है'))
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30_500)
      })
      await waitFor(() => expect((screen.getByTestId('ask-input') as HTMLTextAreaElement).value).toContain('कवर'))
    } finally {
      vi.useRealTimers()
    }
  })

  it('speaks an answer with the browser voice when the server gives no audio, and labels it SIMULATED', async () => {
    const spoken: string[] = []
    win.SpeechSynthesisUtterance = FakeUtterance
    win.speechSynthesis = { speak: vi.fn<(u: FakeUtterance) => void>((u) => spoken.push(`${u.lang}|${u.text}`)), cancel: vi.fn<() => void>() }
    await openAsk()
    type('What is the waiting period?')
    send()
    fireEvent.click(await screen.findByTestId('ask-listen-AQ-000001'))
    await waitFor(() => expect(spoken).toHaveLength(1))
    expect(spoken[0]).toContain('en-IN|')
    expect(spoken[0]).toContain('7 days')
    expect(screen.getByTestId('ask-listen-mode').textContent).toBe('SIMULATED')
  })

  it('keeps the answer as text when nothing can speak', async () => {
    await openAsk()
    type('hello')
    send()
    fireEvent.click(await screen.findByTestId('ask-listen-AQ-000001'))
    await waitFor(() => expect(screen.getByTestId('ask-listen-AQ-000001').getAttribute('data-speaking')).toBe('false'))
    expect(screen.getByTestId('ask-answer-text')).toBeTruthy()
  })
})
