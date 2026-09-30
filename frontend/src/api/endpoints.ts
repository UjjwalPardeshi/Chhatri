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
  ClockState,
  Decision,
  IntegrationStatus,
  MerchantDetail,
  MerchantSummary,
  Message,
  PolicyView,
  ScenarioName,
  Session,
  StateSnapshot,
  VoiceDemoKey,
  ZonePanel,
} from './types'
import { SCENARIO_NAMES } from './types'

export const MIN_SPEED = 1
export const MAX_SPEED = 120
export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024
export const IMAGE_TYPES: readonly string[] = ['image/jpeg', 'image/png', 'image/webp']

const MERCHANT_ID = /^S-\d{4}$/
const CASE_ID = /^C-\d+$/
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

export function createApi(client: ApiClient) {
  return {
    client,
    integrations: () => client.get<IntegrationStatus[]>('/api/integrations'),
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
    cases: (status: CaseStatus | 'ALL', signal?: AbortSignal) =>
      client.get<Case[]>(status === 'ALL' ? '/api/cases' : `/api/cases?status=${status}`, signal),
    caseDetail: (id: string, signal?: AbortSignal) => client.get<Case>(`/api/cases/${assertCaseId(id)}`, signal),
    approve: (id: string, note: string) => client.post<Case>(`/api/cases/${assertCaseId(id)}/approve`, { note }, true),
    decline: (id: string, note: string) => client.post<Case>(`/api/cases/${assertCaseId(id)}/decline`, { note }, true),
    decision: (id: string) => client.get<Decision>(`/api/decisions/${encodeURIComponent(id)}`),
    audit: (after: number, limit: number, signal?: AbortSignal) =>
      client.list<AuditEntry[]>(`/api/audit?after=${after}&limit=${limit}`, signal),
    verifyAudit: () => client.get<AuditVerify>('/api/audit/verify'),
    policy: (signal?: AbortSignal) => client.get<PolicyView>('/api/policy', signal),
    backtest: (signal?: AbortSignal) => client.get<BacktestReport>('/api/backtest', signal),
  }
}

export type Api = ReturnType<typeof createApi>
export type { ListResult }
