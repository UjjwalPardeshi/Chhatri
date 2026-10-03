import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import { integrationRows } from './fixtures'
import { testApi } from './testkit'

afterEach(() => vi.unstubAllEnvs())

describe('mock Telegram channel (telegram_channel)', () => {
  it('starts on WhatsApp, moves a merchant to Telegram once, audits it, and sends on TELEGRAM after', async () => {
    vi.stubEnv('VITE_FEATURES', 'telegram_channel')
    const { api, backend, client } = testApi()
    client.setOfficerToken((await api.session()).officer_token)
    await api.load('illness')
    expect((await api.channel('S-0142')).preferred_channel).toBe('whatsapp')
    expect((await api.setChannel('S-0142', 'telegram')).preferred_channel).toBe('telegram')
    await api.setChannel('S-0142', 'telegram')
    expect(backend.runtime.audit.filter((e) => e.action === 'channel.preference_set')).toHaveLength(1)
    await api.sendText('S-0142', 'hello')
    const outbound = backend.runtime.messages.filter((m) => m.merchant_id === 'S-0142' && m.direction === 'OUTBOUND').at(-1)
    expect(outbound?.channel).toBe('TELEGRAM')
    await api.load('illness')
    expect((await api.channel('S-0142')).preferred_channel).toBe('whatsapp')
    expect(integrationRows(false).some((r) => r.name === 'telegram')).toBe(true)
  })

  it('answers 404 while the flag is off and rejects an unknown channel', async () => {
    vi.stubEnv('VITE_FEATURES', '')
    const { api } = testApi()
    await api.load('monsoon')
    await expect(api.channel('S-0142')).rejects.toBeInstanceOf(ApiError)
    expect(integrationRows(false).some((r) => r.name === 'telegram')).toBe(false)
    vi.stubEnv('VITE_FEATURES', 'telegram_channel')
    expect(() => api.setChannel('S-0142', 'sms' as never)).toThrow(ApiError)
  })
})
