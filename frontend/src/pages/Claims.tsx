/**
 * Claims officer page (SPEC §20 "Claims"): queue on the left, the selected case on the right.
 * The selection is scoped to the replay run (claims/selection.ts) so a scenario switch never asks
 * for a case from the previous run, and the credit delay after an approval comes from the
 * published rules (GET /api/policy, B1 payout_rail_delay_minutes). An approval on a paused replay
 * steps the clock to the end of the payout workflow (useSettle, B2) so the money arrives on screen,
 * and an officer decision is shown with the REFERRED decision it supersedes (SPEC §9.4).
 */
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'

import type { ApiError } from '../api/client'
import type { Case } from '../api/types'
import { CaseDetail } from '../components/claims/CaseDetail'
import { CaseQueue } from '../components/claims/CaseQueue'
import { isStaleRequest, pickCase, queueOrder, runKey, type CaseFilter, type RunCases } from '../components/claims/selection'
import { AsyncView, Loading } from '../components/common/Status'
import { railDelayMinutes } from '../lib/rules'
import { useLive, useLiveEvent } from '../state/live'
import { toApiError, useAsync } from '../state/useAsync'
import { useSettle } from '../state/useSettle'

const FILTERS: readonly { value: CaseFilter; label: string }[] = [
  { value: 'OPEN', label: 'Open' },
  { value: 'ALL', label: 'All' },
]

function NoCase() {
  return (
    <div className="status-box claims__empty">
      <span className="status-box__title">No case selected</span>
      <span>Cases open when a slip needs a human or a merchant disputes an amount.</span>
    </div>
  )
}

export default function Claims() {
  const { api, snapshot, officerReady } = useLive()
  const [params, setParams] = useSearchParams()
  const [filter, setFilter] = useState<CaseFilter>('ALL')
  const [version, setVersion] = useState(0)
  /** The last officer action error, shown only while its case stays selected. */
  const [failure, setFailure] = useState<{ caseId: string; error: ApiError } | null>(null)
  const run = runKey(snapshot?.clock)
  useLiveEvent(['case', 'decision', 'payout'], () => setVersion((v) => v + 1))
  const list = useAsync<RunCases | null>(
    async (signal) => (run === null ? null : { run, filter, cases: queueOrder(await api.cases(filter, signal)) }),
    [api, filter, version, run],
  )
  const policy = useAsync((signal) => api.policy(signal), [api])
  const requested = params.get('case')
  const selected = pickCase(requested, list.data, run)
  const detail = useAsync((signal) => (selected ? api.caseDetail(selected, signal) : Promise.resolve(null)), [api, selected, version, run])
  const supersedes = detail.data?.id === selected ? (detail.data?.decision?.supersedes ?? null) : null
  const referral = useAsync((signal) => (supersedes ? api.decision(supersedes, signal) : Promise.resolve(null)), [api, supersedes])
  const settle = useSettle()
  const actionError = failure && failure.caseId === selected ? failure.error : null
  const stale = isStaleRequest(requested, list.data, run)
  const queue = list.data !== null && list.data.run === run ? list.data : null

  useEffect(() => {
    if (stale) setParams({}, { replace: true })
  }, [stale, setParams])

  const decide = async (item: Case, approve: boolean, note: string) => {
    try {
      const result = await (approve ? api.approve(item.id, note) : api.decline(item.id, note))
      setFailure(null)
      if (result.decision.outcome === 'APPROVED') await settle(item.merchant_id)
    } catch (reason) {
      setFailure({ caseId: item.id, error: toApiError(reason) })
    } finally {
      setVersion((v) => v + 1)
    }
  }

  return (
    <div className="claims">
      <aside className="claims__queue card">
        <header className="claims__queue-head">
          <h2>Claims queue</h2>
          <fieldset className="segmented" aria-label="Filter cases">
            {FILTERS.map((f) => (
              <button key={f.value} type="button" aria-pressed={filter === f.value} className={filter === f.value ? 'is-on' : ''} onClick={() => setFilter(f.value)}>
                {f.label}
              </button>
            ))}
          </fieldset>
        </header>
        <AsyncView {...list} label="Loading cases…">
          {() => <CaseQueue cases={queue?.cases ?? []} selected={selected} now={snapshot?.clock.now ?? ''} onSelect={(id) => setParams({ case: id })} />}
        </AsyncView>
      </aside>
      <section className="claims__detail card">
        {selected ? (
          <AsyncView {...detail} label="Loading case…">
            {(item) =>
              item ? (
                <CaseDetail
                  key={item.id}
                  item={item}
                  now={snapshot?.clock.now ?? ''}
                  officerReady={officerReady}
                  actionError={actionError}
                  delayMinutes={railDelayMinutes(policy.data?.rules)}
                  referral={referral.data?.id === item.decision?.supersedes ? referral.data : null}
                  onDecide={(approve, note) => decide(item, approve, note)}
                  onDismissError={() => setFailure(null)}
                />
              ) : null
            }
          </AsyncView>
        ) : queue === null && list.error === null ? (
          <Loading label="Loading cases…" />
        ) : (
          <NoCase />
        )}
      </section>
    </div>
  )
}
