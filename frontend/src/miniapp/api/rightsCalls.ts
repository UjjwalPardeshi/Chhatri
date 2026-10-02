/**
 * The calls of the rights routes (data-model 5.4 and 5.5), mixed into `createApi`: the grievance ladder, the consent
 * centre, the activity log, the withdrawal and the erase of a slip. Input is validated here, at the client boundary,
 * so a bad id, an empty or over-long complaint or a date that is not a date never reaches the server. The two writes
 * of the consent centre need the officer token, which the demo borrows from the console's session (ADR 0005).
 */
import { ApiError, type ApiClient, type ListResult } from '../../api/client'
import {
  GRIEVANCE_TOPICS,
  MAX_COMPLAINT_CHARS,
  isConsentId,
  isGrievanceId,
  isIsoDate,
  isSlipId,
  parseActivity,
  parseConsents,
  parseForget,
  parseGrievance,
  parseGrievances,
  parseWithdraw,
  type ActivityItem,
  type Consent,
  type ConsentPurpose,
  type ForgetResult,
  type Grievance,
  type GrievanceTopic,
  type StepId,
  type WithdrawResult,
} from './rights'

const MERCHANT_ID = /^S-\d{4}$/
const DECISION_ID = /^D-\d{6,}$/
export const ACTIVITY_PAGE = 50

const invalid = (field: string, reason: string): ApiError => new ApiError('VALIDATION_ERROR', 'Invalid input', 0, { [field]: reason })

function merchantPath(id: string): string {
  if (!MERCHANT_ID.test(id)) throw invalid('merchant_id', 'must look like S-0142')
  return `/api/merchants/${id}`
}

function grievanceId(value: string): string {
  if (!isGrievanceId(value)) throw invalid('grievance_id', 'must look like GR-000001')
  return value
}

export type OpenGrievance = { topic: GrievanceTopic; text: string; lang: 'hi' | 'en'; decision_id?: string }
export type ActivityQuery = { limit?: number; offset?: number; purpose?: ConsentPurpose }
export type ActivityPage = { items: ActivityItem[]; total: number }

export function rightsCalls(client: ApiClient) {
  return {
    /** GET /api/merchants/{id}/grievances (newest first, not paged). */
    grievances: async (merchantId: string, signal?: AbortSignal): Promise<Grievance[]> =>
      parseGrievances((await client.list<unknown>(`${merchantPath(merchantId)}/grievances`, signal)).items),
    /** POST action OPEN. The same merchant, decision and topic while one is open answers the existing grievance (200). */
    openGrievance: async (merchantId: string, request: OpenGrievance): Promise<Grievance> => {
      const text = request.text.trim()
      if (!(GRIEVANCE_TOPICS as readonly string[]).includes(request.topic)) throw invalid('topic', 'choose what the complaint is about')
      if (text.length === 0) throw invalid('text', 'tell us in your own words')
      if (text.length > MAX_COMPLAINT_CHARS) throw invalid('text', `at most ${MAX_COMPLAINT_CHARS} characters`)
      if (request.decision_id !== undefined && !DECISION_ID.test(request.decision_id)) throw invalid('decision_id', 'must look like D-000142')
      return parseGrievance(await client.post<unknown>(`${merchantPath(merchantId)}/grievances`, { action: 'OPEN', ...request, text }))
    },
    /** POST action ESCALATE: `escalateFrom` must be the current step; `filedOn` is the date the merchant says they filed. */
    escalateGrievance: async (merchantId: string, id: string, escalateFrom: StepId, filedOn?: string): Promise<Grievance> => {
      if (filedOn !== undefined && !isIsoDate(filedOn)) throw invalid('filed_on', 'use a date like 2025-08-25')
      const body = { action: 'ESCALATE', grievance_id: grievanceId(id), escalate_from: escalateFrom, ...(filedOn ? { filed_on: filedOn } : {}) }
      return parseGrievance(await client.post<unknown>(`${merchantPath(merchantId)}/grievances`, body))
    },
    /** POST action RESOLVE. */
    resolveGrievance: async (merchantId: string, id: string): Promise<Grievance> =>
      parseGrievance(await client.post<unknown>(`${merchantPath(merchantId)}/grievances`, { action: 'RESOLVE', grievance_id: grievanceId(id) })),
    /** GET /api/merchants/{id}/consents: always the three purposes, in a fixed order. */
    consents: async (merchantId: string, signal?: AbortSignal): Promise<Consent[]> =>
      parseConsents((await client.list<unknown>(`${merchantPath(merchantId)}/consents`, signal)).items),
    /** POST .../consents/{id}/withdraw (officer token): no body; it takes effect at once. */
    withdrawConsent: async (merchantId: string, consentId: string): Promise<WithdrawResult> => {
      if (!isConsentId(consentId)) throw invalid('consent_id', 'must look like CN-000002')
      return parseWithdraw(await client.post<unknown>(`${merchantPath(merchantId)}/consents/${consentId}/withdraw`, {}, true))
    },
    /** GET .../consents/activity: newest first, paged by `limit` and `offset`, with an optional purpose. */
    consentActivity: async (merchantId: string, query: ActivityQuery = {}, signal?: AbortSignal): Promise<ActivityPage> => {
      const params = new URLSearchParams({ limit: String(query.limit ?? ACTIVITY_PAGE), offset: String(query.offset ?? 0) })
      if (query.purpose) params.set('purpose', query.purpose)
      const result: ListResult<unknown> = await client.list<unknown>(`${merchantPath(merchantId)}/consents/activity?${params}`, signal)
      const items = parseActivity(result.items)
      return { items, total: result.meta?.total ?? items.length }
    },
    /** POST .../slips/{slip_id}/forget (officer token): erases one stored slip; the decision and the audit log stay. */
    forgetSlip: async (merchantId: string, slipId: string): Promise<ForgetResult> => {
      if (!isSlipId(slipId)) throw invalid('slip_id', 'must look like MD-000002')
      return parseForget(await client.post<unknown>(`${merchantPath(merchantId)}/slips/${slipId}/forget`, {}, true))
    },
  }
}
