/** Claims officer page (SPEC §20 "Claims"): queue on the left, the selected case on the right. */
import { useState } from 'react'
import { useSearchParams } from 'react-router'

import type { ApiError } from '../api/client'
import type { Case, CaseStatus } from '../api/types'
import { CaseDetail } from '../components/claims/CaseDetail'
import { CaseQueue } from '../components/claims/CaseQueue'
import { AsyncView } from '../components/common/Status'
import { useLive, useLiveEvent } from '../state/live'
import { toApiError, useAsync } from '../state/useAsync'

type Filter = CaseStatus | 'ALL'
const FILTERS: readonly { value: Filter; label: string }[] = [
  { value: 'OPEN', label: 'Open' },
  { value: 'ALL', label: 'All' },
]

export default function Claims() {
  const { api, snapshot, officerReady } = useLive()
  const [params, setParams] = useSearchParams()
  const [filter, setFilter] = useState<Filter>('ALL')
  const [version, setVersion] = useState(0)
  /** The last officer action error, shown only while its case stays selected. */
  const [failure, setFailure] = useState<{ caseId: string; error: ApiError } | null>(null)
  const scenarioKey = `${snapshot?.clock.scenario}|${snapshot?.clock.start}`
  useLiveEvent(['case', 'decision', 'payout'], () => setVersion((v) => v + 1))
  const list = useAsync((signal) => api.cases(filter, signal), [api, filter, version, scenarioKey])
  const selected = params.get('case') ?? list.data?.[0]?.id ?? null
  const detail = useAsync((signal) => (selected ? api.caseDetail(selected, signal) : Promise.resolve(null)), [api, selected, version, scenarioKey])
  const actionError = failure && failure.caseId === selected ? failure.error : null

  const decide = async (item: Case, approve: boolean, note: string) => {
    try {
      await (approve ? api.approve(item.id, note) : api.decline(item.id, note))
      setFailure(null)
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
          {(cases) => <CaseQueue cases={cases} selected={selected} now={snapshot?.clock.now ?? ''} onSelect={(id) => setParams({ case: id })} />}
        </AsyncView>
      </aside>
      <section className="claims__detail card">
        {selected ? (
          <AsyncView {...detail} label="Loading case…">
            {(item) =>
              item ? (
                <CaseDetail
                  item={item}
                  now={snapshot?.clock.now ?? ''}
                  officerReady={officerReady}
                  actionError={actionError}
                  onDecide={(approve, note) => decide(item, approve, note)}
                  onDismissError={() => setFailure(null)}
                />
              ) : null
            }
          </AsyncView>
        ) : (
          <div className="status-box">
            <span className="status-box__title">No case selected</span>
            <span>Cases open when a slip needs a human or a merchant disputes an amount.</span>
          </div>
        )}
      </section>
    </div>
  )
}
