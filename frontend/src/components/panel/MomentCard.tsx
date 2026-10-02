/**
 * The trigger-to-payout moment (fs-08 13.4, behind the console_polish flag): the four minutes from the 17:00 trigger to
 * the money, as one compact card on top of the live map's right panel. It is in the page only while the replay clock is
 * inside the scenario's slow window (content/chapters.ts: the monsoon's 16:58 to 17:06) and while the replay is paused
 * at the end of it (the launcher's 17:06 hold, kept through the moment the pause is being asked for); everywhere else,
 * and for every scenario without a window, it is absent.
 * A track from the window's start to its end carries the chapter ticks and a cursor at the replay clock, and the line
 * above it follows the beat: waiting for the trigger, paying, credited, instalments paused. The numbers come from the
 * snapshot (triggers, kpis) and the published rail delay; the H8 numbers (pending payouts, holiday requests) arrive
 * with the ops summary and their words stay out until then. No endpoint of its own. The card's words are its only copy,
 * kept to one line where it can, because the right panel has no height to spare (design system 8.1).
 */
import type { AreaTrigger, ClockState, Kpis, StateSnapshot } from '../../api/types'
import { CHAPTERS, inWindow, minuteOfDay, SLOW_WINDOWS, type SlowWindow } from '../../content/chapters'
import { hhmm, hhmmAfter } from '../../lib/time'

const PCT = 100
/** A label centred on a tick this far along the track would run past the track's end, so it is end-aligned instead. */
const END_ALIGN_FROM_PCT = 80
const TRIGGER_CHAPTER = 'Trigger'

/** Holiday request outcomes of the ops summary (fs-08 10.3 `holiday_requests_today`). */
export type HolidayCounts = { GRANTED: number; REFUSED: number; NO_RESPONSE: number; REQUESTED: number }
/** The H8 numbers the card shows once they exist (card 6.2): payouts in flight and the holiday requests. Both optional. */
export type MomentOps = { pendingPayouts?: number | null; holidayRequests?: HolidayCounts | null }

export type MomentPhase = 'waiting' | 'paying' | 'credited' | 'instalments'
export type MomentTick = { at: string; label: string; pct: number; passed: boolean; align: 'centre' | 'end' }
export type Moment = {
  phase: MomentPhase
  /** The replay is paused at the end of the window (the 17:06 hold). */
  held: boolean
  window: SlowWindow
  /** The replay clock's place on the track, in percent of the window. */
  pct: number
  ticks: MomentTick[]
  /** The beat's words: the first part is the headline, the rest follow it after a dot. */
  parts: string[]
}

export type MomentInput = {
  clock: Pick<ClockState, 'now' | 'scenario' | 'running'>
  zones: StateSnapshot['zones']
  triggers: StateSnapshot['triggers']
  kpis: Kpis
  /** `payout_rail_delay_minutes` from GET /api/policy; null while unknown, and "credit due" is then left out. */
  railDelayMinutes: number | null
  ops?: MomentOps | null
  /**
   * A pause is on its way (the launcher's 17:06 stop has asked for it and the answer is not back). The clock still says
   * "running" for that moment, and the card must not blink out at the very beat the presenter stops to talk.
   */
  pausing?: boolean
}

function plural(count: number, one: string, many: string = `${one}s`): string {
  return `${count} ${count === 1 ? one : many}`
}

function firstTrigger(triggers: readonly AreaTrigger[]): AreaTrigger | null {
  return triggers.toSorted((a, b) => Date.parse(a.fired_at) - Date.parse(b.fired_at))[0] ?? null
}

/** "17:04" for a time `minutes` after the trigger fired; null when the sum cannot be told. */
function timeAfter(trigger: AreaTrigger | null, minutes: number | null): string | null {
  if (!trigger || minutes === null) return null
  const at = hhmmAfter(trigger.fired_at, minutes)
  return at === '—' ? null : at
}

function holidayLine(counts: HolidayCounts | null | undefined): string | null {
  if (!counts) return null
  const total = counts.GRANTED + counts.REFUSED + counts.NO_RESPONSE + counts.REQUESTED
  if (total === 0) return null
  const outcomes = [`${counts.GRANTED} granted`, ...(counts.REFUSED > 0 ? [`${counts.REFUSED} refused`] : []), ...(counts.NO_RESPONSE > 0 ? [`${counts.NO_RESPONSE} no answer`] : []), ...(counts.REQUESTED > 0 ? [`${counts.REQUESTED} waiting`] : [])]
  return `${plural(total, 'holiday request')}, ${outcomes.join(', ')}`
}

function phaseOf(triggers: readonly AreaTrigger[], kpis: Kpis): MomentPhase {
  if (kpis.instalments_paused > 0) return 'instalments'
  if (kpis.shops_paid > 0) return 'credited'
  return triggers.length > 0 ? 'paying' : 'waiting'
}

function wordsOf(phase: MomentPhase, input: MomentInput, trigger: AreaTrigger | null): string[] {
  const { kpis, triggers, zones, ops, railDelayMinutes } = input
  const shopsPaid = plural(kpis.shops_paid, 'shop')
  if (phase === 'waiting') {
    const checkAt = input.clock.scenario ? CHAPTERS[input.clock.scenario].find((c) => c.label === TRIGGER_CHAPTER)?.at : undefined
    const watching = zones.filter((zone) => zone.status === 'watch').length
    return [checkAt ? `Waiting for the ${checkAt} trigger check` : 'Waiting for a trigger', ...(watching > 0 ? [`${plural(watching, 'zone')} on watch`] : [])]
  }
  if (phase === 'paying') {
    const shops = ops?.pendingPayouts ?? triggers.reduce((sum, t) => sum + t.shops_in_index, 0)
    const due = timeAfter(trigger, railDelayMinutes)
    return [`Triggered at ${hhmm(trigger?.fired_at)}`, `paying ${plural(shops, 'shop')}`, ...(due ? [`credit due ${due}`] : [])]
  }
  if (phase === 'credited') {
    /** The credit time is the trigger plus the KPI's trigger-to-money minutes; the replay clock is not a stand-in for it. */
    const creditedAt = timeAfter(trigger, kpis.trigger_to_money_min)
    return [creditedAt ? `Credited at ${creditedAt}` : 'Credited', `${kpis.total_paid_label} to ${shopsPaid}`]
  }
  /**
   * Once the lender decides (X4, fs-08 13.4) the card says the lender's answers and nothing else: a grant is the pause,
   * and the money is on the ops strip and the KPI tiles beside it, so the line stays one line in presenter type.
   */
  const holiday = holidayLine(ops?.holidayRequests)
  if (holiday) return [holiday]
  return [`${plural(kpis.instalments_paused, 'instalment')} paused`, ...(kpis.shops_paid > 0 ? [`${kpis.total_paid_label} to ${shopsPaid}`] : [])]
}

function tickAt(chapter: { at: string; label: string }, from: number, to: number, now: number): MomentTick | null {
  const minute = minuteOfDay(chapter.at)
  if (minute === null || minute < from || minute > to) return null
  const pct = ((minute - from) / (to - from)) * PCT
  return { at: chapter.at, label: chapter.label, pct, passed: now >= minute, align: pct > END_ALIGN_FROM_PCT ? 'end' : 'centre' }
}

/**
 * The card's state for this replay moment, or null when the card is not in the page: outside the scenario's slow
 * window, except the minute the window ends while the replay is paused there.
 */
export function momentOf(input: MomentInput): Moment | null {
  const slowWindow = input.clock.scenario ? SLOW_WINDOWS[input.clock.scenario] : null
  if (!input.clock.scenario || !slowWindow) return null
  const nowHhmm = hhmm(input.clock.now)
  const now = minuteOfDay(nowHhmm)
  const from = minuteOfDay(slowWindow.from)
  const to = minuteOfDay(slowWindow.to)
  if (now === null || from === null || to === null || to <= from) return null
  const held = (!input.clock.running || input.pausing === true) && now === to
  if (!held && !inWindow(nowHhmm, slowWindow)) return null
  const phase = phaseOf(input.triggers, input.kpis)
  const ticks = CHAPTERS[input.clock.scenario].flatMap((chapter) => tickAt(chapter, from, to, now) ?? [])
  const pct = Math.min(PCT, Math.max(0, ((now - from) / (to - from)) * PCT))
  return { phase, held, window: slowWindow, pct, ticks, parts: wordsOf(phase, input, firstTrigger(input.triggers)) }
}

export function MomentCard(input: MomentInput) {
  const moment = momentOf(input)
  if (!moment) return null
  const [headline, ...rest] = moment.parts
  const now = hhmm(input.clock.now)
  return (
    <section className="card moment" aria-label="Trigger to payout" data-state={moment.phase} data-held={moment.held}>
      {/*
       * One live region that stays mounted from beat to beat: the line inside it is keyed by the beat so its fade replays,
       * and a live region that is replaced rather than changed is not announced.
       */}
      <div className="moment__words" aria-live="polite">
        <p key={moment.phase} className="moment__line">
          <strong>{headline}</strong>
          {rest.length > 0 ? ` · ${rest.join(' · ')}` : null}
        </p>
        {/* The hold is said in words for assistive technology only: a visible tag would cost the panel 26 px it does not have. */}
        {moment.held ? <span className="visually-hidden">{`Replay paused at ${moment.window.to}`}</span> : null}
      </div>
      <div className="moment__rail">
        <progress className="visually-hidden" max={PCT} value={Math.round(moment.pct)} aria-label={`Replay at ${now}, in the window ${moment.window.from} to ${moment.window.to}`} />
        <div className="moment__track" aria-hidden="true">
          <span className="moment__fill" style={{ transform: `scaleX(${moment.pct / PCT})` }} />
          {moment.ticks.map((tick) => (
            <span key={tick.at} className="moment__tick" data-passed={tick.passed} style={{ left: `${tick.pct}%` }} />
          ))}
          <span className="moment__cursor" style={{ left: `${moment.pct}%` }} />
        </div>
        <div className="moment__labels">
          {moment.ticks.map((tick) => (
            <span key={tick.at} className="moment__label" data-align={tick.align} data-passed={tick.passed} title={`${tick.at} ${tick.label}`} style={tick.align === 'centre' ? { left: `${tick.pct}%` } : undefined}>
              {tick.label}
            </span>
          ))}
        </div>
      </div>
    </section>
  )
}
