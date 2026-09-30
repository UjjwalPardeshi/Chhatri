/** Audit log (SPEC §11, §20 "Audit"): the tamper-evident chain, newest first, and "Verify chain". */
import { useCallback, useEffect, useRef, useState } from 'react'

import type { ApiError } from '../api/client'
import type { Api } from '../api/endpoints'
import type { AuditEntry, AuditVerify } from '../api/types'
import { ErrorState, InlineError, Loading } from '../components/common/Status'
import { hhmm, dayLabel } from '../lib/time'
import { useLive, useLiveEvent } from '../state/live'
import { toApiError } from '../state/useAsync'

export const AUDIT_PAGE = 200
const HASH_CHARS = 10

/** Reads every entry after `after`, page by page (GET /api/audit?after=&limit=). */
export async function fetchAuditAfter(api: Api, after: number, signal?: AbortSignal): Promise<AuditEntry[]> {
  const out: AuditEntry[] = []
  let cursor = after
  for (;;) {
    const page = await api.audit(cursor, AUDIT_PAGE, signal)
    out.push(...page.items)
    if (page.items.length < AUDIT_PAGE) return out
    cursor = page.items[page.items.length - 1].seq
  }
}

type RunEntries = { run: string; items: AuditEntry[] }

/** Entries of one scenario run; a new run (reload/reset) starts the log again from seq 0. */
function useAuditEntries() {
  const { api, snapshot } = useLive()
  const [loaded, setLoaded] = useState<RunEntries | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [version, setVersion] = useState(0)
  const lastSeq = useRef({ run: '', seq: 0 })
  const scenarioKey = `${snapshot?.clock.scenario}|${snapshot?.clock.start}`

  useEffect(() => {
    const controller = new AbortController()
    const after = lastSeq.current.run === scenarioKey ? lastSeq.current.seq : 0
    fetchAuditAfter(api, after, controller.signal).then(
      (fresh) => {
        if (controller.signal.aborted) return
        const known = lastSeq.current.run === scenarioKey ? lastSeq.current.seq : 0
        const added = fresh.filter((e) => e.seq > known)
        lastSeq.current = { run: scenarioKey, seq: added.at(-1)?.seq ?? known }
        setLoaded((current) => ({ run: scenarioKey, items: current?.run === scenarioKey ? [...current.items, ...added] : added }))
        setError(null)
      },
      (reason: unknown) => {
        if (!controller.signal.aborted) setError(toApiError(reason))
      },
    )
    return () => controller.abort()
  }, [api, version, scenarioKey])

  const bump = useCallback(() => setVersion((v) => v + 1), [])
  useLiveEvent(['audit'], bump)
  const entries = loaded?.run === scenarioKey ? loaded.items : null
  return { entries, error, reload: bump }
}

function VerifyResult({ result }: { result: AuditVerify }) {
  return result.valid ? (
    <output className="verify verify--ok">
      Chain valid · {result.entries} entries · head <span className="mono">{result.head_hash.slice(0, HASH_CHARS)}…</span>
    </output>
  ) : (
    <output className="verify verify--bad">
      Chain INVALID · first bad entry #{result.first_bad_seq} of {result.entries}
    </output>
  )
}

export default function Audit() {
  const { api } = useLive()
  const { entries, error, reload } = useAuditEntries()
  const [filter, setFilter] = useState('')
  const [verify, setVerify] = useState<AuditVerify | null>(null)
  const [verifyError, setVerifyError] = useState<ApiError | null>(null)
  const [verifying, setVerifying] = useState(false)

  const runVerify = async () => {
    setVerifying(true)
    try {
      setVerify(await api.verifyAudit())
      setVerifyError(null)
    } catch (reason) {
      setVerifyError(toApiError(reason))
    } finally {
      setVerifying(false)
    }
  }
  const needle = filter.trim().toLowerCase()
  const shown = (entries ?? []).filter((e) => needle === '' || `${e.action} ${e.actor} ${e.subject_type} ${e.subject_id}`.toLowerCase().includes(needle)).toReversed()

  return (
    <div className="page">
      <header className="page__head">
        <div>
          <p className="eyebrow">Tamper-evident log</p>
          <h1>Audit log</h1>
          <p className="muted">Every step, with simulated time. Each entry hashes the previous one (sha256), so any edit breaks the chain.</p>
        </div>
        <div className="page__tools">
          <input className="input" placeholder="Filter by action, actor or subject" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter audit entries" />
          <button type="button" className="btn btn--primary" disabled={verifying} onClick={() => void runVerify()}>
            {verifying ? 'Verifying…' : 'Verify chain'}
          </button>
          {verify ? <VerifyResult result={verify} /> : null}
        </div>
      </header>
      {verifyError ? <InlineError error={verifyError} onDismiss={() => setVerifyError(null)} /> : null}
      {error && entries === null ? <ErrorState error={error} title="Could not load the audit log" onRetry={reload} /> : null}
      {error && entries !== null ? <InlineError error={error} onDismiss={reload} /> : null}
      {entries === null && !error ? <Loading label="Loading audit log…" /> : null}
      {entries !== null ? (
        <div className="card table-wrap">
          <table className="table audit-table">
            <thead>
              <tr>
                <th className="num">#</th>
                <th>Simulated time</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Subject</th>
                <th>Hash</th>
                <th>Previous</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((e) => (
                <tr key={e.seq}>
                  <td className="num">{e.seq}</td>
                  <td className="tnum">
                    {dayLabel(e.at)} {hhmm(e.at)}
                  </td>
                  <td>
                    <span className="actor">{e.actor}</span>
                  </td>
                  <td className="mono">{e.action}</td>
                  <td>
                    {e.subject_type} <span className="mono">{e.subject_id}</span>
                  </td>
                  <td className="mono" title={e.hash}>
                    {e.hash.slice(0, HASH_CHARS)}
                  </td>
                  <td className="mono muted" title={e.prev_hash}>
                    {e.prev_hash.slice(0, HASH_CHARS)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {shown.length === 0 ? <p className="status-box">No entries match.</p> : null}
        </div>
      ) : null}
    </div>
  )
}
