/**
 * N5 Complaints and escalation (`screen=grievances`, tab Help; fs-06, screens-and-flows 7.1). The ladders of the
 * merchant's complaints, newest first, each step with the clock that has a source and the words "to be confirmed" where
 * none does. Steps outside Chhatri are marked SIMULATED or self-reported, and the screen says so in one line. The
 * buttons: New complaint, send to the next step, filing guide, mark as solved. A write needs the network (disabled
 * with the reason while offline); a 409 means the grievance moved on, so the list is refreshed and the merchant told.
 */
import { useCallback, useState } from 'react'
import { useLocation } from 'react-router'
import { toast } from 'sonner'

import { ApiError } from '../../api/client'
import { useLive } from '../../state/live'
import { GRIEVANCE_TOPICS, type Grievance, type GrievanceTopic, type LadderStep } from '../api/rights'
import { tr } from '../copy/rights'
import { useGrievances } from '../hooks/useRightsData'
import { useRules } from '../hooks/useRules'
import { t } from '../lib/copy'
import { useMiniapp } from '../shell/MiniappContext'
import { EmptyState, NetworkButton, ResourceScreen } from '../shell/SharedStates'
import { GrievanceCard } from './GrievanceCard'
import { FilingSheet, NewComplaintSheet, type Filing } from './GrievanceSheets'
import type { Escalation } from './grievanceModel'
import { Heading, useRightsNba } from './rightsKit'

function topicHint(state: unknown): GrievanceTopic | null {
  const topic = typeof state === 'object' && state !== null ? (state as { topic?: unknown }).topic : null
  return typeof topic === 'string' && (GRIEVANCE_TOPICS as readonly string[]).includes(topic) ? (topic as GrievanceTopic) : null
}

function failureText(error: unknown, lang: 'hi' | 'en' | 'mr'): string {
  if (error instanceof ApiError && error.status === 409) return tr('grv.error.conflict', lang)
  if (error instanceof ApiError && error.status === 422 && 'decision_id' in error.fields) return t('grv.error.no_decision', lang)
  if (error instanceof ApiError && error.status === 422 && 'topic' in error.fields && error.fields.topic.includes('review')) return t('grv.error.no_review', lang)
  return t('error.generic', lang)
}

export function Grievances() {
  const { lang, merchantId, now } = useMiniapp()
  const { api } = useLive()
  const { state: routeState } = useLocation()
  const resource = useGrievances(merchantId)
  const rules = useRules()
  const [composing, setComposing] = useState<GrievanceTopic | 'open' | null>(topicHint(routeState))
  const [filing, setFiling] = useState<Filing | null>(null)
  const [busy, setBusy] = useState(false)
  const { reload } = resource

  const run = useCallback(
    (action: () => Promise<unknown>, done: string | null, after?: () => void) => {
      setBusy(true)
      action()
        .then(() => {
          if (done) toast(done)
          after?.()
        })
        .catch((error: unknown) => toast.error(failureText(error, lang)))
        .finally(() => {
          setBusy(false)
          reload()
        })
    },
    [lang, reload],
  )

  const onSend = (topic: GrievanceTopic, text: string) => run(() => api.openGrievance(merchantId, { topic, text, lang: lang === 'en' ? 'en' : 'hi' }), tr('grv.sent', lang), () => setComposing(null))
  const onResolve = (grievance: Grievance) => run(() => api.resolveGrievance(merchantId, grievance.grievance_id), tr('grv.solved', lang))
  const onEscalate = (grievance: Grievance, next: Escalation) => {
    if (next.filing) setFiling({ grievance, from: next.from, to: nextStepOf(grievance), mode: 'file' })
    else run(() => api.escalateGrievance(merchantId, grievance.grievance_id, next.from), null)
  }
  const onGuide = (grievance: Grievance, step: LadderStep) => setFiling({ grievance, from: step.id, to: null, mode: 'guide' })
  const onSave = (current: Filing, date: string) => run(() => api.escalateGrievance(merchantId, current.grievance.grievance_id, current.from, date), null, () => setFiling(null))

  const open = (resource.data ?? []).some((g) => g.status === 'OPEN' && g.ladder_steps.some((s) => s.id === 'PAYTM_DISPUTE' && s.state === 'ACTIVE'))
  const slaHours = rules.data?.dispute_sla_hours ?? null
  const ready = resource.state === 'ready' || resource.state === 'empty'
  const startNew = () => setComposing('open')
  useRightsNba(
    !ready ? null : open && slaHours !== null ? { id: 'grievances_open', sentence: 'nba.grievances.open', button: 'grv.new', params: { sla_hours: slaHours }, onAction: startNew } : { id: 'grievances_new', sentence: 'nba.grievances.new', button: 'nba.grievances.new.btn', onAction: startNew },
  )

  const actions = { busy, onEscalate, onResolve, onGuide }
  const newButton = (
    <NetworkButton data-testid="grv-new" onClick={startNew}>
      {tr('grv.new', lang)}
    </NetworkButton>
  )
  const initial = composing === 'open' ? null : composing
  return (
    <>
      <ResourceScreen name="grievances" resource={resource} empty={<EmptyState message={tr('empty.grievances', lang)}>{newButton}</EmptyState>}>
        {(list) => (
          <>
            <Heading>{t('grv.title', lang)}</Heading>
            <p className="text-sm text-ink-2">{tr('grv.intro', lang)}</p>
            <div className="flex flex-col gap-3">
              {list.map((grievance) => (
                <GrievanceCard key={grievance.grievance_id} grievance={grievance} lang={lang} now={now} actions={actions} />
              ))}
            </div>
            <p data-testid="grv-outside" className="text-xs text-ink-3">
              {tr('grv.outside', lang)}
            </p>
            {newButton}
          </>
        )}
      </ResourceScreen>
      {composing !== null ? <NewComplaintSheet open initialTopic={initial} lang={lang} busy={busy} onClose={() => setComposing(null)} onSend={onSend} /> : null}
      {filing ? <FilingSheet filing={filing} lang={lang} today={(now ?? '').slice(0, 10)} busy={busy} onClose={() => setFiling(null)} onSave={onSave} /> : null}
    </>
  )
}

/** The step the escalation moves to: the one after the current step of the ladder. */
function nextStepOf(grievance: Grievance): LadderStep['id'] | null {
  const at = grievance.ladder_steps.findIndex((step) => step.id === grievance.current_step)
  return grievance.ladder_steps[at + 1]?.id ?? null
}

