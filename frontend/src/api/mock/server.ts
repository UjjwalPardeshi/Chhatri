/**
 * Mock API server for development
 * Intercepts fetch calls and serves fixtures
 */

import {
  createStateSnapshot,
  mockCase,
  mockClockState,
  mockDecision,
  mockMessages,
  mockPolicy,
  mockAnil,
  mockPayout,
  mockZones,
  mockBacktest,
} from './fixtures'
import type { Envelope, ErrorEnvelope } from '../types'

export function initMockServer(): void {
  if (typeof window === 'undefined') return

  const originalFetch = window.fetch

  window.fetch = async (
    input: RequestInfo | URL,
    init?: RequestInit
  ): Promise<Response> => {
    const url = typeof input === 'string' ? input : input.toString()

    // Only intercept API and webhook calls
    if (!url.includes('/api/') && !url.includes('/webhooks/')) {
      return originalFetch(input, init)
    }

    // Handle mock server
    const response = handleMockRequest(url, init)
    if (response) {
      return response
    }

    // Fallback to real fetch
    return originalFetch(input, init)
  }
}

function handleMockRequest(
  url: string,
  init?: RequestInit
): Response | undefined {
  // Remove protocol and domain
  const path = url.replace(/^https?:\/\/[^/]+/, '')

  // Health check
  if (path === '/api/health') {
    return createJsonResponse({
      ok: true,
      data: {
        status: 'ok',
        version: '0.1.0-mock',
        seed: 20251019,
      },
    })
  }

  // Session (demo mode)
  if (path === '/api/session') {
    return createJsonResponse({
      ok: true,
      data: {
        officer_token: 'demo-token-12345',
      },
    })
  }

  // Integrations
  if (path === '/api/integrations') {
    return createJsonResponse({
      ok: true,
      data: [
        {
          name: 'sarvam_stt',
          mode: 'SIMULATED',
          detail: 'Running in mock mode',
        },
        {
          name: 'sarvam_tts',
          mode: 'SIMULATED',
          detail: 'Running in mock mode',
        },
        {
          name: 'sales_data',
          mode: 'SIMULATED',
          detail: 'Deterministic simulator',
        },
        {
          name: 'alerts',
          mode: 'SIMULATED',
          detail: 'Scripted monsoon replay',
        },
        {
          name: 'payout_rail',
          mode: 'SIMULATED',
          detail: 'Instant settlement',
        },
      ],
    })
  }

  // Preflight
  if (path === '/api/preflight') {
    return createJsonResponse({
      ok: true,
      data: [
        { name: 'artifacts', ok: true, detail: 'Ready' },
        { name: 'scenario', ok: true, detail: 'Loaded' },
        { name: 'integrations', ok: true, detail: 'Ready' },
        { name: 'clock', ok: true, detail: 'Running' },
      ],
    })
  }

  // State snapshot
  if (path === '/api/state') {
    return createJsonResponse({
      ok: true,
      data: createStateSnapshot(),
    })
  }

  // Zones
  if (path === '/api/geo/zones') {
    return createJsonResponse({
      ok: true,
      data: {
        type: 'FeatureCollection',
        features: Object.values(mockZones).map((zone) => ({
          type: 'Feature',
          properties: {
            id: zone.zone_id,
            ward: zone.ward,
            name: zone.name,
            shops: zone.shops,
          },
          geometry: {
            type: 'Point',
            coordinates: [72.8, 19.0],
          },
        })),
      },
    })
  }

  // Hexes
  if (path === '/api/geo/hexes') {
    return createJsonResponse({
      ok: true,
      data: {
        type: 'FeatureCollection',
        features: [],
      },
    })
  }

  // Zone detail
  const zoneMatch = path.match(/^\/api\/zones\/([ZZ]\d+)$/)
  if (zoneMatch) {
    const zoneId = zoneMatch[1]
    const zone = mockZones[zoneId]

    if (!zone) {
      return createErrorResponse('Zone not found', 404)
    }

    return createJsonResponse({
      ok: true,
      data: {
        zone,
        triggered: zone.status === 'triggered',
        rows: [
          { label: 'Alert', value: zone.alert?.headline_en || 'No alert' },
          { label: 'Sales', value: `${100 - (100 - zone.index_pct!)}% of expected for 3 hours` },
          { label: 'Cover', value: `${zone.shops} of ${zone.shops} prepaid` },
          { label: 'Paid', value: '17:04, with the settlement' },
          { label: 'Total', value: '₹58,900 · instalments paused' },
        ],
        explanation: 'Explanation text here',
        shops_paid: zone.shops,
        total_paid_paise: 5890000,
        total_paid_label: '₹58,900',
        hourly: [
          { hour: '14:00', index_pct: 37 },
          { hour: '15:00', index_pct: 37 },
          { hour: '16:00', index_pct: 37 },
          { hour: '17:00', index_pct: 37 },
        ],
      },
    })
  }

  // Merchants
  if (path === '/api/merchants?zone_id=Z7&q=&limit=10&offset=0') {
    return createJsonResponse({
      ok: true,
      data: [mockAnil],
      meta: { total: 1, limit: 10, offset: 0 },
    })
  }

  // Merchant detail
  if (path === '/api/merchants/S-0142') {
    return createJsonResponse({
      ok: true,
      data: mockAnil,
    })
  }

  // Merchant messages
  if (path === '/api/merchants/S-0142/messages') {
    return createJsonResponse({
      ok: true,
      data: mockMessages,
    })
  }

  // Decisions
  if (path === '/api/decisions/D-000001') {
    return createJsonResponse({
      ok: true,
      data: mockDecision,
    })
  }

  // Payouts
  if (path === '/api/payouts?zone_id=&date=') {
    return createJsonResponse({
      ok: true,
      data: [mockPayout],
    })
  }

  // Cases
  if (path === '/api/cases?status=') {
    return createJsonResponse({
      ok: true,
      data: [mockCase],
    })
  }

  if (path === '/api/cases/C-2291') {
    return createJsonResponse({
      ok: true,
      data: mockCase,
    })
  }

  // Policy
  if (path === '/api/policy') {
    return createJsonResponse({
      ok: true,
      data: mockPolicy,
    })
  }

  // Backtest
  if (path === '/api/backtest') {
    return createJsonResponse({
      ok: true,
      data: mockBacktest,
    })
  }

  // Audit
  if (path === '/api/audit?after=0&limit=200') {
    return createJsonResponse({
      ok: true,
      data: [],
    })
  }

  // Audit verify
  if (path === '/api/audit/verify') {
    return createJsonResponse({
      ok: true,
      data: {
        valid: true,
        entries: 0,
        head_hash: '0'.repeat(64),
        first_bad_seq: null,
      },
    })
  }

  // Replay controls
  if (path === '/api/replay/load' && init?.method === 'POST') {
    return createJsonResponse({
      ok: true,
      data: createStateSnapshot(),
    })
  }

  if (path === '/api/replay/play' && init?.method === 'POST') {
    return createJsonResponse({
      ok: true,
      data: mockClockState,
    })
  }

  // Stream endpoint returns 200 but actual streaming is mocked
  if (path === '/api/stream') {
    // In a real mock, we'd return a ReadableStream or EventSource
    return new Response(
      'data: {"type":"scenario","id":"1","at":"2025-08-19T17:00:00+05:30","data":{"clock":' +
        JSON.stringify(mockClockState) +
        '}}\n\n',
      {
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
        },
      }
    )
  }

  return undefined
}

function createJsonResponse<T>(data: Envelope<T>): Response {
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
    },
  })
}

function createErrorResponse(message: string, status: number): Response {
  const data: ErrorEnvelope = {
    ok: false,
    error: {
      code: 'MOCK_ERROR',
      message,
    },
  }

  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
    },
  })
}

// Start the mock server if enabled
if (import.meta.env.VITE_USE_MOCKS) {
  initMockServer()
}
