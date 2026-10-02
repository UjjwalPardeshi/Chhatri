/**
 * Ask Chhatri (N2, N4, fs-05, screens section 5): a question box, a thread of answers and, with `n4_voice`, the mic.
 * Chhatri explains and the rules decide every payout. Every answer carries clause chips (H17), the facts it is based
 * on with source badges, one next action chosen by the backend (H21), the scam banner when the check fired (H19) and
 * the mode and provider (H26). The composer takes the place of the next-step bar. Empty, thinking, error, offline,
 * SIMULATED and FALLBACK all have their line. The screen is behind `n2_ask_chhatri`; the URL treats `screen=ask` as
 * Home while the flag is off.
 */
import { LoaderCircle } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { isFeatureEnabled } from '../../features'
import type { AskAnswer, AskRequest, NextActionKind } from '../api/ask'
import { useVoiceQuestion } from '../components/voiceQuestion'
import { useSpeaker } from '../components/voiceSpeaker'
import { ta } from '../copy/ask'
import { useClaims } from '../hooks/useMiniappData'
import { t } from '../lib/copy'
import { useMiniapp } from '../shell/MiniappContext'
import { Button } from '../ui/button'
import { AskAnswerCard } from './AskAnswerCard'
import { AskComposer } from './AskComposer'
import { AskSuggestions, type SuggestionFacts } from './AskSuggestions'
import { useAskThread, type AskEntry } from './AskThread'

const ELAPSED_AFTER_S = 2
const CONNECTION_CODES: ReadonlySet<string> = new Set(['NETWORK_ERROR', 'TIMEOUT'])

function Thinking({ lang, onCancel }: { lang: 'hi' | 'en'; onCancel: () => void }) {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const timer = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(timer)
  }, [])
  return (
    <output data-testid="ask-thinking" className="flex flex-col gap-2 rounded-lg border bg-card p-3">
      <span className="flex items-center gap-2 text-sm">
        <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
        {ta('ask.thinking', lang)}
      </span>
      {seconds >= ELAPSED_AFTER_S ? <span className="num text-xs text-ink-3">{ta('ask.elapsed', lang, { seconds })}</span> : null}
      <Button data-testid="ask-cancel" variant="outline" className="self-start" onClick={onCancel}>
        {ta('ask.btn.cancel', lang)}
      </Button>
    </output>
  )
}

function Failed({ entry, lang, onRetry }: { entry: AskEntry; lang: 'hi' | 'en'; onRetry: () => void }) {
  const offline = entry.error !== null && CONNECTION_CODES.has(entry.error.code)
  return (
    <div data-testid="ask-failed" role="alert" className="flex flex-col items-start gap-2 rounded-lg border border-blocked bg-blocked-soft p-3">
      <p className="text-sm font-medium">{offline ? ta('ASK_OFFLINE', lang) : t('error.generic', lang)}</p>
      {entry.error === null || offline ? null : <p className="text-xs text-ink-3">{t('error.code', lang, { code: entry.error.code })}</p>}
      <Button data-testid="ask-retry" variant="outline" onClick={onRetry}>
        {t('error.retry', lang)}
      </Button>
    </div>
  )
}

function suggestionFacts(claims: ReturnType<typeof useClaims>, hasLoan: boolean): SuggestionFacts | null {
  if (claims.state === 'loading' || claims.state === 'error') return claims.state === 'error' ? { hasDecision: false, hasPaidDecision: false, hasLoan } : null
  const items = claims.data ?? []
  return { hasDecision: items.some((c) => c.decision_id !== null), hasPaidDecision: items.some((c) => c.decision_id !== null && c.outcome === 'APPROVED'), hasLoan }
}

export function Ask() {
  const { lang, merchantId, merchant, now, online, url } = useMiniapp()
  const askLang = lang === 'en' ? 'en' : 'hi'
  const claims = useClaims(merchantId)
  const thread = useAskThread(merchantId, now)
  const [text, setText] = useState('')
  const field = useRef<HTMLTextAreaElement | null>(null)
  const voiceOn = isFeatureEnabled('n4_voice')
  const voice = useVoiceQuestion({ merchantId, lang: askLang, text, setText })
  const speaker = useSpeaker(merchantId)
  const facts = suggestionFacts(claims, Boolean(merchant.data?.loan))
  const latest: AskAnswer | null = thread.entries.findLast((e) => e.answer !== null)?.answer ?? null

  async function send(question: string): Promise<void> {
    const trimmed = question.trim()
    const request: AskRequest = voice.sttId !== null && voiceOn ? { question: trimmed, lang: askLang, stt_id: voice.sttId, confirmed_mentions: voice.confirmedIds } : { question: trimmed, lang: askLang }
    const answered = await thread.ask(request)
    if (answered) {
      setText('')
      voice.reset()
    }
  }

  function next(kind: NextActionKind): void {
    const paid = (claims.data ?? []).find((c) => c.claim_id !== null && c.outcome === 'APPROVED')
    if (kind === 'SEE_CLAIM' || kind === 'TRACK_CASE') url.go({ screen: 'claims' })
    else if (kind === 'SEE_COVER') url.go({ screen: 'home' })
    else if (kind === 'GET_COVER') url.go({ screen: 'buy' })
    else if (kind === 'TALK_TO_TEAM' && paid?.claim_id) url.go({ screen: 'claim', claim: paid.claim_id })
    else field.current?.focus()
  }

  const empty = thread.entries.length === 0
  const state = !online ? 'offline' : empty ? (facts === null ? 'loading' : 'empty') : 'ready'
  return (
    <section data-testid="screen-ask" data-state={state} aria-busy={state === 'loading' ? true : undefined} className="flex min-h-full flex-col">
      <div className="flex flex-1 flex-col gap-4 p-4">
        {latest?.mode === 'FALLBACK' ? <p data-testid="ask-fallback-line" className="rounded-lg bg-fallback-soft px-3 py-2 text-xs text-fallback">{ta('fb.ask', lang)}</p> : null}
        {empty ? <AskSuggestions lang={lang} facts={facts} disabled={thread.asking || !online} onPick={(q) => void send(q)} /> : null}
        <ol aria-live="polite" className="flex flex-col gap-4">
          {thread.entries.map((entry) => (
            <li key={entry.key} data-testid="ask-entry" data-status={entry.status} className="flex flex-col gap-2">
              <p data-testid="ask-question" className="max-w-[85%] self-end whitespace-pre-line rounded-2xl rounded-br-sm bg-accent px-3 py-2 text-sm text-foreground">
                <span className="sr-only">{ta('ask.you', lang)}: </span>
                {entry.request.question}
              </p>
              {entry.status === 'pending' ? <Thinking lang={askLang} onCancel={() => thread.cancel(entry.key)} /> : null}
              {entry.status === 'failed' ? <Failed entry={entry} lang={askLang} onRetry={() => thread.retry(entry.key)} /> : null}
              {entry.answer ? <AskAnswerCard answer={entry.answer} answeredAt={entry.answeredAt} lang={lang} speaker={voiceOn ? speaker : null} onNext={next} /> : null}
            </li>
          ))}
        </ol>
      </div>
      <div className="sticky bottom-0 z-10">
        <AskComposer lang={lang} text={text} onText={setText} onSend={() => void send(text)} field={field} online={online} sending={thread.asking} voice={voiceOn ? voice : null} />
      </div>
    </section>
  )
}
