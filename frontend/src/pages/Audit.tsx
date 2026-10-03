/**
 * Audit log (SPEC §11, §20 "Audit"): the tamper-evident chain, newest first, grouped by simulated
 * minute (AuditTable), and "Verify chain". While the run has only its first few entries, a card
 * says what will appear here and starts the storm replay.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

import type { ApiError } from '../api/client'
import type { Api } from '../api/endpoints'
import type { AuditEntry, AuditVerify } from '../api/types'
import { AuditTable } from '../components/audit/AuditTable'
import { searchText } from '../components/audit/auditText'
import { ErrorState, InlineError, Loading } from '../components/common/Status'
import { LaunchButton } from '../components/overview/LaunchButton'
import { LaunchError } from '../components/overview/LaunchError'
import { useLive, useLiveEvent } from '../state/live'
import { toApiError } from '../state/useAsync'
import { useLaunch } from '../state/useLaunch'

export const AUDIT_PAGE = 200
/** Up to this many entries the run has barely started (scenario load, an alert or two). */
export const EARLY_ENTRIES = 5
const EARLY_KEYS = ['audit-storm'] as const

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
    <output className="verify verify--ok" title={`Latest fingerprint ${result.head_hash}`}>
      Chain valid · {result.entries} entries · none changed since written
    </output>
  ) : (
    <output className="verify verify--bad">
      Chain INVALID · first bad entry #{result.first_bad_seq} of {result.entries} · it was changed after it was written
    </output>
  )
}

function EarlyRun() {
  const launcher = useLaunch()
  return (
    <section className="card audit-early" aria-label="The log fills as the replay runs">
      <div>
        <h2>The log fills as the replay runs</h2>
        <p className="muted">Every trigger, decision, payout and instalment pause gets an entry here, each one hashing the one before it.</p>
        <LaunchError launcher={launcher} keys={EARLY_KEYS} />
      </div>
      <LaunchButton launcher={launcher} id="audit-storm" target="stormLive" label="Watch the 17:00 storm" busyLabel="Loading the storm…" />
    </section>
  )
}

export default function Audit() {
  const { api } = useLive()
  const { entries, error, reload } = useAuditEntries()
  const [filter, setFilter] = useState('')
  const [verify, setVerify] = useState<AuditVerify | null>(null)
  const [verified, setVerified] = useState(0)
  const [verifyError, setVerifyError] = useState<ApiError | null>(null)
  const [verifying, setVerifying] = useState(false)

  const runVerify = async () => {
    setVerifying(true)
    try {
      const result = await api.verifyAudit()
      setVerify(result)
      setVerified((n) => (result.valid ? n + 1 : 0))
      setVerifyError(null)
    } catch (reason) {
      setVerifyError(toApiError(reason))
    } finally {
      setVerifying(false)
    }
  }
  const needle = filter.trim().toLowerCase()
  const shown = (entries ?? []).filter((e) => needle === '' || searchText(e).includes(needle)).toReversed()

  return (
    <div className="page">
      <header className="page__head">
        <div>
          <p className="eyebrow">Tamper-evident log</p>
          <h1>Audit log</h1>
          <p className="muted">Every step Chhatri took, in plain words and simulated time. Each entry carries a fingerprint of the one before it (sha256), so changing any entry breaks the chain.</p>
        </div>
        <div className="page__tools">
          <input className="input" placeholder="Search: payout, lender, S-0142…" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter audit entries" />
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
      {entries !== null && entries.length <= EARLY_ENTRIES && needle === '' ? <EarlyRun /> : null}
      {entries !== null ? (
        <div className="card audit-wrap">
          <AuditTable entries={shown} verified={verified} />
          {shown.length === 0 ? <p className="status-box">No entries match.</p> : null}
        </div>
      ) : null}
    </div>
  )
}
