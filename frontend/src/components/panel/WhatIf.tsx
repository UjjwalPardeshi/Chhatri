/**
 * The H24 what-if drawer (fs-08 11, flag h24_whatif): it opens over the right panel of /live, says plainly that
 * nothing is saved, and lets a judge change the rule's inputs (the alert, the three hourly sales, the shops in the
 * index, "already triggered today") while the deterministic engine recomputes the verdict. The hour is pinned when the
 * drawer opens, so a running replay does not move it; "Latest hour" repins it. Every change waits 150 ms and aborts the
 * request in flight, because a slider sends several a second. The words come from the server's answer, never from here.
 */
import { useEffect, useRef, useState, type CSSProperties } from 'react'

import { ApiError } from '../../api/client'
import type { WhatIfAlert, WhatIfArea, WhatIfOverrides } from '../../api/opsWhatIf'
import { hhmm, hhmmAfter } from '../../lib/time'
import { useLive } from '../../state/live'
import { toApiError } from '../../state/useAsync'
import { ALERT_CHOICES, evaluatedLine, exampleLine, isUntouched, resultLine, rulesLine, shownHours, SLIDER_MAX_PCT, WHATIF_DEBOUNCE_MS, withHour } from './whatIfModel'

export type WhatIfDrawerProps = {
  zoneId: string
  /** The zone's covered shops: the top of the shops control. */
  maxShops: number
  /** A covered merchant of this zone, to price one shop's payout; null when there is none. */
  exampleMerchantId: string | null
  onClose: () => void
}

function ConditionRows({ answer }: { answer: WhatIfArea }) {
  return (
    <table className="whatif__conditions">
      <caption className="visually-hidden">The five conditions of the trigger rule, what happened and what if</caption>
      <thead>
        <tr>
          <th scope="col">Condition</th>
          <th scope="col">What happened</th>
          <th scope="col">What if</th>
        </tr>
      </thead>
      <tbody>
        {answer.conditions.map((c) => (
          <tr key={c.code} data-flip={c.baseline.met !== c.scenario.met ? 'true' : undefined}>
            <th scope="row">{c.label_en}</th>
            <Verdict side={c.baseline} />
            <Verdict side={c.scenario} />
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Verdict({ side }: { side: { met: boolean; observed: string } }) {
  return (
    <td data-met={side.met}>
      <span className="whatif__mark" aria-label={side.met ? 'Met' : 'Not met'}>
        {side.met ? '✓' : '✗'}
      </span>{' '}
      {side.observed}
    </td>
  )
}

function Controls({ answer, draft, maxShops, set }: { answer: WhatIfArea | null; draft: WhatIfOverrides; maxShops: number; set: (next: WhatIfOverrides) => void }) {
  const baseline = answer?.baseline ?? null
  const alert = draft.alert ?? baseline?.alert ?? 'NONE'
  const hours = shownHours(draft, baseline)
  const floor = answer?.fixed.index_floor_pct ?? 50
  const shops = draft.shops_in_index ?? baseline?.shops_in_index ?? 0
  const already = draft.already_triggered_today ?? baseline?.already_triggered_today ?? false
  return (
    <div className="whatif__controls">
      <fieldset className="whatif__field">
        <legend>Alert</legend>
        <div className="whatif__choices">
          {ALERT_CHOICES.map((choice) => (
            <button key={choice.value} type="button" className="btn" aria-pressed={alert === choice.value} onClick={() => set({ ...draft, alert: choice.value as WhatIfAlert })}>
              {choice.label}
            </button>
          ))}
        </div>
      </fieldset>
      {hours.map((value, index) => (
        <label key={index} className="whatif__field whatif__slider" style={{ '--floor': `${(floor / Math.max(SLIDER_MAX_PCT, value)) * 100}%` } as CSSProperties}>
          <span>
            Hour {index + 1}
            {answer ? ` (${hhmmAfter(answer.window.start, index * 60)})` : ''}: <strong>{value}%</strong>
          </span>
          <input type="range" min={0} max={Math.max(SLIDER_MAX_PCT, value)} step={1} value={value} aria-label={`Hour ${index + 1} sales as a percent of expected`} onChange={(e) => set(withHour(draft, baseline, index, Number(e.target.value)))} />
          <span className="whatif__floor">{floor}% floor</span>
        </label>
      ))}
      <label className="whatif__field">
        <span>Shops in the index</span>
        <input type="number" min={0} max={maxShops} value={shops} onChange={(e) => set({ ...draft, shops_in_index: Math.min(maxShops, Math.max(0, Math.trunc(Number(e.target.value) || 0))) })} />
      </label>
      <label className="whatif__field whatif__check">
        <input type="checkbox" checked={already} onChange={(e) => set({ ...draft, already_triggered_today: e.target.checked })} />
        <span>Already triggered today</span>
      </label>
    </div>
  )
}

function useWhatIf(zoneId: string, exampleMerchantId: string | null, draft: WhatIfOverrides) {
  const { api } = useLive()
  const [answer, setAnswer] = useState<WhatIfArea | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)
  /** The hour pinned when the first answer arrives (fs-08 11.1); null asks for the latest hour. */
  const pinned = useRef<string | null>(null)
  const draftKey = JSON.stringify(draft)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    const timer = setTimeout(
      () => {
        const body = { zone_id: zoneId, ...(pinned.current ? { at: pinned.current } : {}), ...(isUntouched(draft) ? {} : { overrides: draft }), ...(exampleMerchantId ? { example_merchant_id: exampleMerchantId } : {}) }
        api.whatIfArea(body, controller.signal).then(
          (value) => {
            if (controller.signal.aborted) return
            pinned.current ??= value.at
            setAnswer(value)
            setError(null)
            setLoading(false)
          },
          (reason: unknown) => {
            if (controller.signal.aborted) return
            setError(toApiError(reason))
            setLoading(false)
          },
        )
      },
      isUntouched(draft) ? 0 : WHATIF_DEBOUNCE_MS,
    )
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `draftKey` is the draft's value
  }, [api, zoneId, exampleMerchantId, draftKey, tick])

  return {
    answer,
    error,
    loading,
    retry: () => setTick((t) => t + 1),
    latestHour: () => {
      pinned.current = null
      setTick((t) => t + 1)
    },
  }
}

export function WhatIfDrawer({ zoneId, maxShops, exampleMerchantId, onClose }: WhatIfDrawerProps) {
  const [draft, setDraft] = useState<WhatIfOverrides>({})
  const { answer, error, loading, retry, latestHour } = useWhatIf(zoneId, exampleMerchantId, draft)
  const heading = useRef<HTMLHeadingElement | null>(null)
  useEffect(() => {
    heading.current?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])
  const noWindow = error?.code === 'conflict'
  return (
    <aside className="whatif" aria-label={`What if for zone ${zoneId}`} aria-busy={loading}>
      <header className="whatif__head">
        <h2 ref={heading} tabIndex={-1}>
          What if… {answer ? `Zone ${answer.zone_id} · ${answer.zone_name}` : `Zone ${zoneId}`}
        </h2>
        <button type="button" className="btn" onClick={onClose} aria-label="Close what if">
          Close
        </button>
      </header>
      <p className="whatif__readonly">Read-only: nothing is saved</p>
      {answer ? (
        <p className="whatif__evaluated">
          {evaluatedLine(answer, hhmm)}{' '}
          <button type="button" className="whatif__link" onClick={latestHour}>
            Latest hour
          </button>
        </p>
      ) : null}
      {error ? (
        <div className="whatif__error" role="alert">
          {noWindow ? 'No completed 3-hour window yet. Play the replay a little further.' : `Cannot compute: ${error.describe()}`}{' '}
          {noWindow ? null : (
            <button type="button" className="btn" onClick={retry}>
              Retry
            </button>
          )}
        </div>
      ) : null}
      {!answer && !error ? <p className="whatif__loading">Computing…</p> : null}
      {answer ? (
        <>
          <Controls answer={answer} draft={draft} maxShops={maxShops} set={setDraft} />
          <button type="button" className="btn" disabled={isUntouched(draft)} onClick={() => setDraft({})}>
            Back to what happened
          </button>
          <ConditionRows answer={answer} />
          <p className="whatif__result" data-fires={answer.scenario.fires} aria-live="polite">
            <span>What happened: {resultLine(answer.baseline, true)}</span>
            <strong>{resultLine(answer.scenario, false)}</strong>
          </p>
          {answer.example ? <p className="whatif__example">{exampleLine(answer.example)}. Amount arithmetic only, not a claim decision.</p> : null}
          <p className="whatif__rules">{rulesLine(answer.fixed)}</p>
          <p className="whatif__rules">
            {answer.computed_by}. {loading ? 'Recomputing…' : 'Nothing was stored.'}
          </p>
        </>
      ) : null}
    </aside>
  )
}
