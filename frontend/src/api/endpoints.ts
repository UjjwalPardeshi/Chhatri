/**
 * Typed wrappers for every console route of SPEC §19. Inputs are validated here (the client-side
 * boundary) so a malformed id or time never reaches the server.
 */
import type { FeatureCollection } from 'geojson'

import { ApiError, type ApiClient, type ListResult } from './client'
import type {
  AuditEntry,
  AuditVerify,
  BacktestReport,
  Case,
  CaseStatus,
  ChannelView,
  ClaimItem,
  ClockState,
  Cover,
  Decision,
  IntegrationStatus,
  MerchantDetail,
  MerchantSummary,
  Message,
  OfficerResult,
  PaytmAck,
  PolicyView,
  PrecheckAction,
  PrecheckConfirm,
  PrecheckInput,
  PreferredChannel,
  PremiumLinkResult,
  Receipt,
  ScenarioName,
  Session,
  SlipPrecheck,
  StateSnapshot,
  VoiceDemoKey,
  ZonePanel,
} from './types'
import { parseOpsSummary, parseWhatIf, type OpsSummary, type WhatIfArea, type WhatIfRequest } from './opsWhatIf'
import { SCENARIO_NAMES } from './types'
import { askCalls } from '../miniapp/api/askCalls'
import { rightsCalls } from '../miniapp/api/rightsCalls'
import { CONSENT_PURPOSES, type ConsentPurpose } from '../miniapp/api/rights'
import { EVALS_PATH, parseEvalsSummary, type EvalsSummary } from './evals'

export const MIN_SPEED = 1
export const MAX_SPEED = 120
export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024
export const IMAGE_TYPES: readonly string[] = ['image/jpeg', 'image/png', 'image/webp']

const MERCHANT_ID = /^S-\d{4}$/
const CASE_ID = /^C-\d+$/
const DECISION_ID = /^D-\d{6,}$/
const PRECHECK_ID = /^PC-\d{6,}$/
const LINK_ID = /^[A-Za-z0-9_-]{1,64}$/
const ZONE_ID = /^Z\d{1,2}$/
const HHMM = /^([01]\d|2[0-3]):[0-5]\d$/

function invalid(field: string, reason: string): ApiError {
  return new ApiError('VALIDATION_ERROR', 'Invalid input', 0, { [field]: reason })
}

export function assertMerchantId(id: string): string {
  if (!MERCHANT_ID.test(id)) throw invalid('merchant_id', 'must look like S-0142')
  return id
}

function assertCaseId(id: string): string {
  if (!CASE_ID.test(id)) throw invalid('case_id', 'must look like C-2291')
  return id
}

function assertDecisionId(id: string): string {
  if (!DECISION_ID.test(id)) throw invalid('decision_id', 'must look like D-000142')
  return id
}

function assertPrecheckId(id: string): string {
  if (!PRECHECK_ID.test(id)) throw invalid('precheck_id', 'must look like PC-000001')
  return id
}

function assertLinkId(id: string): string {
  if (!LINK_ID.test(id)) throw invalid('link_id', 'must be a payment link id such as sim-7BFFBE')
  return id
}

function assertZoneId(id: string): string {
  if (!ZONE_ID.test(id)) throw invalid('zone_id', 'must look like Z7')
  return id
}

export function isScenarioName(value: string): value is ScenarioName {
  return (SCENARIO_NAMES as readonly string[]).includes(value)
}

export function isHhmm(value: string): boolean {
  return HHMM.test(value)
}

export function clampSpeed(speed: number): number {
  if (!Number.isFinite(speed)) throw invalid('speed', 'must be a number')
  return Math.min(MAX_SPEED, Math.max(MIN_SPEED, Math.round(speed)))
}

export function validateImage(file: File): void {
  if (!IMAGE_TYPES.includes(file.type)) throw invalid('file', 'photo must be JPEG, PNG or WebP')
  if (file.size > MAX_UPLOAD_BYTES) throw invalid('file', 'photo must be 5 MB or smaller')
}

export function validateAudio(blob: Blob): void {
  if (blob.size === 0) throw invalid('file', 'recording is empty')
  if (blob.size > MAX_UPLOAD_BYTES) throw invalid('file', 'recording must be 5 MB or smaller')
}

const merchantPath = (id: string): string => `/api/merchants/${assertMerchantId(id)}`

/** The consent block of a purchase (n6_consents, fs-07 9.5): the ticked purposes and the notice version the merchant read. */
export type PurchaseConsent = { consents: readonly ConsentPurpose[]; notice_version: string }

const NOTICE_VERSION = /^[A-Za-z0-9._-]{1,32}$/

function assertNoticeVersion(version: string): string {
  if (!NOTICE_VERSION.test(version)) throw invalid('notice_version', 'must be the notice version, such as notice-1')
  return version
}

function consentBody(consent: PurchaseConsent | undefined): Partial<PurchaseConsent> {
  if (consent === undefined) return {}
  const known: readonly string[] = CONSENT_PURPOSES
  if (consent.consents.length > CONSENT_PURPOSES.length || consent.consents.some((p) => !known.includes(p))) throw invalid('consents', 'must name the purposes of the notice')
  return { consents: [...new Set(consent.consents)], notice_version: assertNoticeVersion(consent.notice_version) }
}

export function createApi(client: ApiClient) {
  return {
    client,
    integrations: () => client.get<IntegrationStatus[]>('/api/integrations'),
    /** X6: force a component to its fallback path (`true`) or release it (`false`); answers the updated row. */
    setFallback: (component: string, force: boolean) => {
      if (!/^[a-z][a-z0-9_]*$/.test(component)) throw invalid('component', 'unknown component')
      return client.post<IntegrationStatus>(`/api/integrations/${component}/fallback`, { force }, true)
    },
    session: () => client.get<Session>('/api/session'),
    state: (signal?: AbortSignal) => client.get<StateSnapshot>('/api/state', signal),
    zonesGeo: () => client.get<FeatureCollection>('/api/geo/zones'),
    hexesGeo: () => client.get<FeatureCollection>('/api/geo/hexes'),
    zonePanel: (zoneId: string, signal?: AbortSignal) =>
      client.get<ZonePanel>(`/api/zones/${assertZoneId(zoneId)}`, signal),
    load: (scenario: string) => {
      if (!isScenarioName(scenario)) throw invalid('scenario', 'unknown scenario')
      return client.post<ClockState>('/api/replay/load', { scenario })
    },
    play: (speed: number) => client.post<ClockState>('/api/replay/play', { speed: clampSpeed(speed) }),
    pause: () => client.post<ClockState>('/api/replay/pause'),
    step: (minutes: number) => {
      if (!Number.isInteger(minutes) || minutes < 1) throw invalid('minutes', 'must be a whole number ≥ 1')
      return client.post<ClockState>('/api/replay/step', { minutes })
    },
    seek: (to: string) => {
      if (!isHhmm(to)) throw invalid('to', 'use HH:MM')
      return client.post<ClockState>('/api/replay/seek', { to })
    },
    reset: () => client.post<ClockState>('/api/replay/reset'),
    merchant: (id: string, signal?: AbortSignal) => client.get<MerchantDetail>(merchantPath(id), signal),
    merchants: (query: string) => client.list<MerchantSummary[]>(`/api/merchants?${query}`),
    messages: (id: string, signal?: AbortSignal) => client.get<Message[]>(`${merchantPath(id)}/messages`, signal),
    /** The merchant's preferred channel and each channel's mode (flag telegram_channel). */
    channel: (id: string, signal?: AbortSignal) => client.get<ChannelView>(`${merchantPath(id)}/channel`, signal),
    /** Choose WhatsApp or Telegram for this merchant's notifications (officer token, as the other demo writes). */
    setChannel: (id: string, channel: PreferredChannel) => {
      if (channel !== 'whatsapp' && channel !== 'telegram') throw invalid('channel', 'whatsapp or telegram')
      return client.post<ChannelView>(`${merchantPath(id)}/channel`, { channel }, true)
    },
    sendText: (id: string, text: string) => {
      const trimmed = text.trim()
      if (trimmed.length === 0) throw invalid('text', 'type a message first')
      return client.post<unknown>(`${merchantPath(id)}/messages`, { text: trimmed })
    },
    sendVoiceDemo: (id: string, key: VoiceDemoKey) => client.post<unknown>(`${merchantPath(id)}/voice-demo`, { key }),
    sendVoice: (id: string, blob: Blob, filename: string) => {
      validateAudio(blob)
      const form = new FormData()
      form.append('file', blob, filename)
      return client.postForm<unknown>(`${merchantPath(id)}/voice`, form)
    },
    sendPhoto: (id: string, file: File) => {
      validateImage(file)
      const form = new FormData()
      form.append('file', file, file.name)
      return client.postForm<unknown>(`${merchantPath(id)}/photo`, form)
    },
    sendSampleSlip: (id: string, sample: string) => client.post<unknown>(`${merchantPath(id)}/photo`, { sample }),
    /** N3 (data-model 5.3): read a slip and run the gate. Nothing is decided until `confirmSlipPrecheck`. */
    slipPrecheck: (id: string, input: PrecheckInput) => {
      const path = `${merchantPath(id)}/slip-precheck`
      if ('file' in input) {
        validateImage(input.file)
        const form = new FormData()
        form.append('file', input.file, input.file.name)
        if (input.lang) form.append('lang', input.lang)
        if (input.consent) form.append('consent', 'true')
        if (input.notice_version) form.append('notice_version', assertNoticeVersion(input.notice_version))
        return client.postForm<SlipPrecheck>(path, form)
      }
      const ok = input.consent ? { consent: true, notice_version: assertNoticeVersion(input.notice_version ?? '') } : {}
      return client.post<SlipPrecheck>(path, { ...(input.sample ? { sample: input.sample } : {}), ...(input.lang ? { lang: input.lang } : {}), ...ok })
    },
    confirmSlipPrecheck: (id: string, precheckId: string, action: PrecheckAction) =>
      client.post<PrecheckConfirm>(`${merchantPath(id)}/slip-precheck/${assertPrecheckId(precheckId)}/confirm`, { action }),
    cases: (status: CaseStatus | 'ALL', signal?: AbortSignal) =>
      client.get<Case[]>(status === 'ALL' ? '/api/cases' : `/api/cases?status=${status}`, signal),
    caseDetail: (id: string, signal?: AbortSignal) => client.get<Case>(`/api/cases/${assertCaseId(id)}`, signal),
    /** SPEC §19: the officer routes answer with the new decision and the resolved case. */
    approve: (id: string, note: string) => client.post<OfficerResult>(`/api/cases/${assertCaseId(id)}/approve`, { note }, true),
    decline: (id: string, note: string) => client.post<OfficerResult>(`/api/cases/${assertCaseId(id)}/decline`, { note }, true),
    decision: (id: string, signal?: AbortSignal) => client.get<Decision>(`/api/decisions/${encodeURIComponent(id)}`, signal),
    /** The mini-app's three read routes (data-model 5.1 and 5.8). Strict parsing happens in `miniapp/api/parse.ts`. */
    cover: (id: string, signal?: AbortSignal) => client.get<Cover>(`${merchantPath(id)}/cover`, signal),
    claims: (id: string, signal?: AbortSignal) => client.list<ClaimItem[]>(`${merchantPath(id)}/claims`, signal),
    receipt: (decisionId: string, signal?: AbortSignal) => client.get<Receipt>(`/api/decisions/${assertDecisionId(decisionId)}/receipt`, signal),
    /** Quote cover and make the (simulated) payment link. Needs the officer token: the demo borrows the console's session. */
    premiumLink: (merchantId: string, consent?: PurchaseConsent) =>
      client.post<PremiumLinkResult>('/api/premium/link', { merchant_id: assertMerchantId(merchantId), ...consentBody(consent) }, true),
    /** The simulated paid callback of the payment link (no token; the real Paytm posts the same fields). */
    paytmWebhook: (linkId: string) => {
      const link = assertLinkId(linkId)
      return client.post<PaytmAck>('/api/webhooks/paytm', { link_id: link, status: 'TXN_SUCCESS', txn_id: `SIM-${link}` })
    },
    audit: (after: number, limit: number, signal?: AbortSignal) =>
      client.list<AuditEntry[]>(`/api/audit?after=${after}&limit=${limit}`, signal),
    verifyAudit: () => client.get<AuditVerify>('/api/audit/verify'),
    policy: (signal?: AbortSignal) => client.get<PolicyView>('/api/policy', signal),
    backtest: (signal?: AbortSignal) => client.get<BacktestReport>('/api/backtest', signal),
    /** H8 (flag h8_ops_strip): counts at the replay clock. Parsed strictly: the kinds add up, the labels are the paise. */
    opsSummary: async (signal?: AbortSignal): Promise<OpsSummary> => parseOpsSummary(await client.get<unknown>('/api/ops/summary', signal)),
    /** H24 (flag h24_whatif): read-only, nothing is saved. A slider sends several of these a second, so it takes a signal. */
    whatIfArea: async (request: WhatIfRequest, signal?: AbortSignal): Promise<WhatIfArea> =>
      parseWhatIf(await client.post<unknown>('/api/whatif/area', { ...request, zone_id: assertZoneId(request.zone_id) }, false, signal)),
    /** Ask Chhatri and voice (data-model 5.2 and 5.11): `ask`, `voiceStt` and `voiceTts`. */
    ...askCalls(client),
    /** N5 and N6 (data-model 5.4 and 5.5): the grievance ladder, the consent centre, the activity log and "forget my slip". */
    ...rightsCalls(client),
    /** H25 (flag h25_evals, data-model 5.10): the stored evaluation run, or NOT MEASURED. Parsed strictly. */
    evalsSummary: async (signal?: AbortSignal): Promise<EvalsSummary> => parseEvalsSummary(await client.get<unknown>(EVALS_PATH, signal)),
  }
}

export type Api = ReturnType<typeof createApi>
export type { ListResult }
