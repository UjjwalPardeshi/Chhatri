/**
 * The two sheets of the complaints screen. The new-complaint sheet (screens-and-flows 7.1): a topic chip picks the
 * respondent from a fixed lookup (never a model), one line says who answers, free text of at most 500 characters,
 * Send, and the note that the lookup is a guide. A second tap on Send is ignored while the first is on its way. The
 * filing sheet is for the steps outside Chhatri (Bima Bharosa and the Ombudsman): what the step is, that the merchant
 * files it herself, what to keep ready, and the date she says she filed, which Chhatri records and never checks.
 */
import { useId, useRef, useState } from 'react'

import { GRIEVANCE_TOPICS, MAX_COMPLAINT_CHARS, TOPIC_RESPONDENT, type Grievance, type GrievanceTopic, type StepId } from '../api/rights'
import { tr, type RightsCopyKey } from '../copy/rights'
import { cn } from '../lib/cn'
import type { Lang } from '../lib/lang'
import { NetworkButton } from '../shell/SharedStates'
import { Button } from '../ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '../ui/sheet'
import { Textarea } from '../ui/textarea'
import { respondentKey } from './grievanceModel'

type NewProps = { open: boolean; lang: Lang; initialTopic: GrievanceTopic | null; busy: boolean; onClose: () => void; onSend: (topic: GrievanceTopic, text: string) => void }

export function NewComplaintSheet({ open, lang, initialTopic, busy, onClose, onSend }: NewProps) {
  const [topic, setTopic] = useState<GrievanceTopic | null>(initialTopic)
  const [text, setText] = useState('')
  const labelId = useId()
  const trimmed = text.trim()
  const ready = topic !== null && trimmed.length > 0 && trimmed.length <= MAX_COMPLAINT_CHARS
  return (
    <Sheet open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
      <SheetContent side="bottom" showCloseButton={false} data-testid="grv-new-sheet" aria-describedby={undefined} className="max-h-[90%] gap-0 overflow-y-auto rounded-t-2xl pb-2">
        <SheetHeader>
          <SheetTitle className="text-md">{tr('grv.topic.title', lang)}</SheetTitle>
        </SheetHeader>
        <div className="flex flex-col gap-3 px-4 pb-2">
          <fieldset className="m-0 flex min-w-0 flex-wrap gap-2 p-0">
            <legend className="sr-only">{tr('grv.topic.title', lang)}</legend>
            {GRIEVANCE_TOPICS.map((id) => (
              <button
                key={id}
                type="button"
                aria-pressed={topic === id}
                data-testid={`grv-topic-${id}`}
                onClick={() => setTopic(id)}
                className={cn('min-h-11 rounded-full border px-4 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50', topic === id ? 'border-primary bg-primary text-primary-foreground' : 'bg-card text-foreground')}
              >
                {tr(`grv.topic.${id}` as RightsCopyKey, lang)}
              </button>
            ))}
          </fieldset>
          {topic ? (
            <p data-testid="grv-who" className="rounded-lg bg-secondary p-3 text-sm text-secondary-foreground">
              {tr(respondentKey(TOPIC_RESPONDENT[topic]), lang)}
            </p>
          ) : null}
          <label id={labelId} htmlFor="grv-text" className="text-sm font-medium">
            {tr('grv.text.label', lang)}
          </label>
          <Textarea id="grv-text" data-testid="grv-text" aria-labelledby={labelId} value={text} maxLength={MAX_COMPLAINT_CHARS} rows={4} onChange={(event) => setText(event.target.value)} />
          <p className="text-xs text-ink-3">
            {text.length} / {MAX_COMPLAINT_CHARS}
          </p>
          <NetworkButton data-testid="grv-send" size="lg" disabled={!ready || busy} onClick={() => (topic ? onSend(topic, trimmed) : undefined)}>
            {tr('grv.btn.submit', lang)}
          </NetworkButton>
          <p className="text-xs text-ink-3">{tr('grv.router.note', lang)}</p>
          <Button data-testid="grv-new-close" variant="outline" onClick={onClose}>
            {tr('grv.btn.close', lang)}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  )
}

export type Filing = { grievance: Grievance; from: StepId; to: StepId | null; mode: 'file' | 'guide' }
type FilingProps = { filing: Filing | null; lang: Lang; today: string; busy: boolean; onClose: () => void; onSave: (filing: Filing, date: string) => void }

export function FilingSheet({ filing, lang, today, busy, onClose, onSave }: FilingProps) {
  const [date, setDate] = useState(today)
  const closeRef = useRef<HTMLButtonElement>(null)
  const step: StepId | null = filing ? (filing.to ?? filing.from) : null
  const { grievance } = filing ?? { grievance: null }
  return (
    <Sheet open={filing !== null} onOpenChange={(next) => (next ? undefined : onClose())}>
      <SheetContent side="bottom" showCloseButton={false} data-testid="grv-filing-sheet" aria-describedby={undefined} className="max-h-[90%] gap-0 overflow-y-auto rounded-t-2xl pb-2" onOpenAutoFocus={(event) => { event.preventDefault(); closeRef.current?.focus() }}>
        <SheetHeader>
          <SheetTitle className="text-md">{step ? tr(`grv.step.${step}` as RightsCopyKey, lang) : ''}</SheetTitle>
          <SheetDescription className="text-sm">{step ? tr(`grv.what.${step}` as RightsCopyKey, lang) : ''}</SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-3 px-4 pb-2">
          <p className="text-sm">{tr('grv.delivery.SELF_REPORTED', lang)}</p>
          <p className="text-sm font-medium">{tr('grv.portal', lang)}</p>
          {grievance?.decision_id && grievance.case_id ? <p data-testid="grv-bring" className="text-sm">{tr('grv.bring', lang, { decision_id: grievance.decision_id, case_id: grievance.case_id })}</p> : null}
          <p className="text-xs text-ink-3">{tr('grv.contact.placeholder', lang)}</p>
          {filing?.mode === 'file' ? (
            <>
              <label htmlFor="grv-filed" className="text-sm font-medium">
                {tr('grv.filed.label', lang)}
              </label>
              <input id="grv-filed" data-testid="grv-filed" type="date" value={date} max={today} onChange={(event) => setDate(event.target.value)} className="min-h-11 rounded-md border bg-background px-3 text-md" />
              <NetworkButton data-testid="grv-save-date" size="lg" disabled={busy || date === ''} onClick={() => (filing ? onSave(filing, date) : undefined)}>
                {tr('grv.btn.save_date', lang)}
              </NetworkButton>
            </>
          ) : null}
          <Button ref={closeRef} data-testid="grv-filing-close" variant="outline" onClick={onClose}>
            {tr('grv.btn.close', lang)}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  )
}
