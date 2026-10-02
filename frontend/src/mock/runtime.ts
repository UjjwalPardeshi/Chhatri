/**
 * Mock runtime: one per loaded scenario (SPEC §3: ids, store, audit and event bus reset on load).
 * Holds the simulated clock minute, the records created so far, a tamper-evident audit chain
 * (SPEC §11: sha256 over canonical JSON, recorded_at excluded) and the simulated-time scheduler
 * (binding decision B1: jobs run at decision time + offset, in (at, seq) order).
 */
import type {
  AreaTrigger,
  AuditEntry,
  Case,
  CoverQuote,
  Decision,
  FeedItem,
  HolidayRequest,
  InstalmentPause,
  Kpis,
  Message,
  MessageKind,
  Payout,
  PayoutCard,
  PremiumPayment,
  SseEventMap,
  SseEventType,
} from '../api/types'
import { formatInr } from '../lib/money'
import type { Bilingual } from './catalogue'
import type { StoredCover } from './endpoints/cover'
import { isoAt, type ScenarioDef } from './scenarios'
import { canonicalJson, sha256Hex } from './sha256'
import type { ZoneMeta } from './zones'

export type Emit = <K extends SseEventType>(type: K, data: SseEventMap[K], at: string) => void

export const GENESIS_HASH = '0'.repeat(64)
export const FIRST_CASE_NUMBER = 2291

type Job = { at: number; seq: number; name: string; run: () => void }

export type ZoneTotals = { shops: number; decidedMin: number; paidPaise: number; creditedAt: string | null; paused: number }

export type Conversation = { checkinSent: boolean; illnessReported: boolean; claimId: string | null }

/** A holiday request as the mock keeps it: the API row plus the merchant it belongs to (the row is served under that merchant). */
export type MockHolidayRequest = HolidayRequest & { merchant_id: string }

export type OutboundSpec = {
  kind: MessageKind
  text: Bilingual | null
  card?: PayoutCard
  mediaUrl?: string
  meta?: Message['meta']
  direction?: Message['direction']
  channel?: Message['channel']
}

export class MockRuntime {
  readonly scenario: ScenarioDef
  readonly zones: readonly ZoneMeta[]
  minute: number
  running = false
  speed: number
  decisions: Decision[] = []
  payouts: Payout[] = []
  pauses: InstalmentPause[] = []
  /** Every EDI holiday request and the lender's answer (X4); grants also have a pause. Empty while the flag is off. */
  holidayRequests: MockHolidayRequest[] = []
  /** True while the lender component is forced to FALLBACK (card 4.5): the mock lender then gives no answer. */
  lenderForced = false
  messages: Message[] = []
  cases: Case[] = []
  audit: AuditEntry[] = []
  feed: FeedItem[] = []
  triggers: AreaTrigger[] = []
  explanations: Record<string, string> = {}
  zoneTotals = new Map<string, ZoneTotals>()
  /** Covers bought through a payment link during this load; the seeded pilot covers live in `endpoints/cover.ts`. */
  covers = new Map<string, StoredCover>()
  quotes: CoverQuote[] = []
  premiums: PremiumPayment[] = []
  /** Paytm transaction ids already handled, so a repeated paid callback is a `duplicate` and changes nothing. */
  paidTransactions = new Set<string>()
  conversations = new Map<string, Conversation>()
  kpis: Kpis = { zones_triggered: 0, shops_paid: 0, trigger_to_money_min: null, total_paid_paise: 0, total_paid_label: formatInr(0), instalments_paused: 0 }
  private jobs: Job[] = []
  private counters = new Map<string, number>()
  private jobSeq = 0
  private caseNumber = FIRST_CASE_NUMBER
  private readonly emitFn: Emit
  private readonly wallClock: () => string

  constructor(scenario: ScenarioDef, zones: readonly ZoneMeta[], speed: number, emit: Emit, wallClock: () => string) {
    this.scenario = scenario
    this.zones = zones
    this.minute = scenario.startMin
    this.speed = speed
    this.emitFn = emit
    this.wallClock = wallClock
  }

  get nowIso(): string {
    return isoAt(this.scenario.day, this.minute)
  }

  emit<K extends SseEventType>(type: K, data: SseEventMap[K]): void {
    this.emitFn(type, data, this.nowIso)
  }

  /** Deterministic ids per prefix (SPEC §3): D-000001, P-000001, M-000001 … */
  nextId(prefix: string): string {
    const next = (this.counters.get(prefix) ?? 0) + 1
    this.counters.set(prefix, next)
    return `${prefix}-${String(next).padStart(6, '0')}`
  }

  /**
   * Moves a prefix's counter on, so the next id is `lastUsed + 1` (it never moves back). The monsoon replay numbers
   * Anil's claim, decision and payout 142, as the backend does after the 141 shops of Z3 (data-model 5.1).
   */
  advanceIds(prefix: string, lastUsed: number): void {
    this.counters.set(prefix, Math.max(this.counters.get(prefix) ?? 0, lastUsed))
  }

  nextCaseId(): string {
    const id = `C-${this.caseNumber}`
    this.caseNumber += 1
    return id
  }

  conversation(merchantId: string): Conversation {
    const existing = this.conversations.get(merchantId)
    if (existing) return existing
    const created: Conversation = { checkinSent: false, illnessReported: false, claimId: null }
    this.conversations.set(merchantId, created)
    return created
  }

  schedule(at: number, name: string, run: () => void): void {
    this.jobSeq += 1
    this.jobs.push({ at, seq: this.jobSeq, name, run })
    this.jobs.sort((a, b) => a.at - b.at || a.seq - b.seq)
  }

  /** Runs every job due at or before the current minute (jobs may schedule more jobs). */
  runDue(): number {
    let ran = 0
    while (this.jobs.length > 0 && this.jobs[0].at <= this.minute) {
      const job = this.jobs.shift() as Job
      job.run()
      ran += 1
    }
    return ran
  }

  pendingJobs(): number {
    return this.jobs.length
  }

  record(actor: string, action: string, subjectType: string, subjectId: string, data: Record<string, unknown>): AuditEntry {
    const prev = this.audit.length > 0 ? this.audit[this.audit.length - 1].hash : GENESIS_HASH
    const body = { seq: this.audit.length + 1, at: this.nowIso, actor, action, subject_type: subjectType, subject_id: subjectId, data, prev_hash: prev }
    const entry: AuditEntry = { ...body, recorded_at: this.wallClock(), hash: sha256Hex(canonicalJson(body)) }
    this.audit.push(entry)
    this.emit('audit', { seq: entry.seq, action, actor, subject_type: subjectType, subject_id: subjectId })
    return entry
  }

  addFeed(type: string, textEn: string, refs: { zone_id?: string; merchant_id?: string } = {}): void {
    this.feed.push({ id: this.feed.length + 1, at: this.nowIso, type, text_en: textEn, ...refs })
  }

  send(merchantId: string, spec: OutboundSpec): Message {
    const message: Message = {
      id: this.nextId('M'),
      merchant_id: merchantId,
      direction: spec.direction ?? 'OUTBOUND',
      channel: spec.channel ?? 'SIMULATOR',
      kind: spec.kind,
      text_hi: spec.text?.hi ?? null,
      text_en: spec.text?.en || null,
      audio_url: null,
      media_url: spec.mediaUrl ?? null,
      card: spec.card ?? null,
      created_at: this.nowIso,
      meta: spec.meta ?? {},
    }
    this.messages.push(message)
    this.emit('message', { message })
    const actor = message.direction === 'INBOUND' ? `merchant:${merchantId}` : 'ai-agent'
    this.record(actor, message.direction === 'INBOUND' ? 'message.received' : 'message.sent', 'message', message.id, { kind: message.kind })
    return message
  }

  setKpis(update: Partial<Kpis>): void {
    const next = { ...this.kpis, ...update }
    this.kpis = { ...next, total_paid_label: formatInr(next.total_paid_paise) }
    this.emit('kpis', { kpis: this.kpis })
  }

  replaceCase(updated: Case): void {
    this.cases = this.cases.map((c) => (c.id === updated.id ? updated : c))
    this.emit('case', { case: updated })
  }
}
