/**
 * The frontend half of the contract test (data-model 6.3, card 3.8 N1-T21): every example under
 * `src/api/contract/` is replayed against the in-browser mock. The example and the mock's answer must both pass the
 * strict parser, have the same shape (keys and value types, recursively) and agree on the example's `exact` fields.
 * The backend half (`backend/tests/api/test_contract_examples.py`) runs the same examples against the real app, so
 * the mock cannot drift away from the product without one of the two failing.
 */
import { readdirSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { afterEach, describe, expect, it } from 'vitest'

import { parseClaims, parseCover, parsePremiumLink, parseReceipt } from '../miniapp/api/parse'
import type { MockBackend } from './backend'
import { createMockFetch } from './fetch'
import { MOCK_OFFICER_TOKEN } from './fixtures'
import { testBackend } from './testkit'

type Step = { method: string; path: string; body?: unknown; auth?: 'officer' }
type Example = {
  name: string
  description: string
  scenario: string
  at: string
  setup: Step[]
  request: Step
  exact: string[]
  response: { status: number; body: Record<string, unknown> }
}

const DIR = resolve(__dirname, '../api/contract')
const FILES = readdirSync(DIR).filter((f) => f.endsWith('.json')).toSorted()
const load = (file: string): Example => JSON.parse(readFileSync(resolve(DIR, file), 'utf8')) as Example

let backend: MockBackend
afterEach(() => backend?.dispose())

type Answer = { status: number; body: Record<string, unknown> }

async function send(fetcher: ReturnType<typeof createMockFetch>, step: Step): Promise<Answer> {
  const headers: Record<string, string> = step.auth === 'officer' ? { Authorization: `Bearer ${MOCK_OFFICER_TOKEN}` } : {}
  const res = await fetcher(step.path, { method: step.method, headers, ...(step.body === undefined ? {} : { body: JSON.stringify(step.body) }) })
  return { status: res.status, body: (await res.json()) as Record<string, unknown> }
}

async function replay(example: Example): Promise<Answer> {
  backend = testBackend()
  const fetcher = createMockFetch(backend)
  await send(fetcher, { method: 'POST', path: '/api/replay/load', body: { scenario: example.scenario } })
  await send(fetcher, { method: 'POST', path: '/api/replay/seek', body: { to: example.at } })
  for (const step of example.setup) expect((await send(fetcher, step)).status, `setup ${step.method} ${step.path}`).toBe(200)
  return send(fetcher, example.request)
}

/** The strict parser for the example's route, or null for a route with no view model (the Paytm acknowledgement). */
function parserFor(path: string): ((raw: unknown) => unknown) | null {
  if (path.endsWith('/cover')) return parseCover
  if (path.endsWith('/claims')) return parseClaims
  if (path.endsWith('/receipt')) return parseReceipt
  if (path === '/api/premium/link') return parsePremiumLink
  return null
}

/** The view model of a 200 answer through its strict parser, and null where there is nothing to parse. */
function parsed(example: Example, body: Record<string, unknown>): unknown {
  const parse = parserFor(example.request.path)
  return example.response.status === 200 && parse ? parse(body.data) : null
}

function kindOf(value: unknown): string {
  if (value === null) return 'null'
  return Array.isArray(value) ? 'array' : typeof value
}

/** Differences in keys and value types. Lists are compared pairwise and must be empty together. */
function shapeDiff(a: unknown, b: unknown, path: string): string[] {
  if (kindOf(a) !== kindOf(b)) return [`${path}: ${kindOf(a)} against ${kindOf(b)}`]
  if (Array.isArray(a) && Array.isArray(b)) {
    if ((a.length === 0) !== (b.length === 0)) return [`${path}: one list is empty`]
    return Array.from({ length: Math.min(a.length, b.length) }, (_, i) => shapeDiff(a[i], b[i], `${path}.${i}`)).flat()
  }
  if (typeof a === 'object' && a !== null && typeof b === 'object' && b !== null) {
    const left = a as Record<string, unknown>
    const right = b as Record<string, unknown>
    const keys = [...new Set([...Object.keys(left), ...Object.keys(right)])]
    return keys.flatMap((key) => (key in left && key in right ? shapeDiff(left[key], right[key], `${path}.${key}`) : [`${path}.${key}: only in the ${key in left ? 'example' : 'mock'}`]))
  }
  return []
}

function pick(value: unknown, path: string): unknown {
  return path.split('.').reduce<unknown>((node, key) => (node !== null && typeof node === 'object' ? (node as Record<string, unknown>)[key] : undefined), value)
}

describe('contract examples', () => {
  it('cover the five mini-app routes with a request, a scenario, a replay time and a response', () => {
    const routes = new Set(FILES.map((f) => load(f).request.path.replace(/S-\d{4}|D-\d{6}|D-\d+/g, '{id}')))
    expect([...routes].toSorted()).toEqual([
      '/api/decisions/{id}/receipt',
      '/api/merchants/{id}/claims',
      '/api/merchants/{id}/cover',
      '/api/premium/link',
      '/api/webhooks/paytm',
    ])
    expect(FILES.length).toBeGreaterThanOrEqual(11)
    for (const file of FILES) {
      const example = load(file)
      expect(file, 'the file name is the example name').toBe(`${example.name}.json`)
      expect(Object.keys(example).toSorted()).toEqual(['at', 'description', 'exact', 'name', 'request', 'response', 'scenario', 'setup'])
    }
  })

  it.each(FILES)('%s: every exact path exists in the example', (file) => {
    const example = load(file)
    for (const path of example.exact) expect(pick(example.response.body, path), `${example.name} ${path}`).not.toBeUndefined()
  })

  it.each(FILES)('%s: the example passes the strict parser', (file) => {
    const example = load(file)
    expect(() => parsed(example, example.response.body)).not.toThrow()
  })

  it.each(FILES)('%s: the mock answers the same way', async (file) => {
    const example = load(file)
    const answer = await replay(example)
    expect(answer.status, 'status').toBe(example.response.status)
    expect(() => parsed(example, answer.body), 'the mock answer passes the parser').not.toThrow()
    expect(shapeDiff(example.response.body, answer.body, 'body'), 'same shape').toEqual([])
    for (const path of example.exact) expect(pick(answer.body, path), `exact ${path}`).toEqual(pick(example.response.body, path))
  })
})
