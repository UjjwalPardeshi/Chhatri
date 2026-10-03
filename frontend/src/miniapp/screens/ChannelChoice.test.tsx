/** The chat app choice on Settings (flag telegram_channel): WhatsApp or Telegram for Chhatri's messages. */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MockBackend } from '../../mock/backend'
import { MOCK_OFFICER_TOKEN } from '../../mock/fixtures'
import { testApi } from '../../mock/testkit'
import { renderStandalone } from '../shell/shellKit'

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  window.localStorage.clear()
})
afterEach(() => {
  backend?.dispose()
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
})

async function openSettings(features: string) {
  vi.stubEnv('VITE_FEATURES', features)
  const kit = testApi()
  backend = kit.backend
  kit.client.setOfficerToken(MOCK_OFFICER_TOKEN)
  await kit.api.load('monsoon')
  renderStandalone('/merchant/S-0142/app?lang=en&screen=settings', kit.backend, kit.api)
  await screen.findByTestId('screen-language')
  return kit
}

describe('ChannelChoice', () => {
  it('moves the messages to Telegram, says the chat is not linked yet and that Telegram is simulated here', async () => {
    const kit = await openSettings('n1_miniapp,telegram_channel')
    expect(await screen.findByTestId('channel-choice')).toBeTruthy()
    expect(screen.getByText('Messages from Chhatri')).toBeTruthy()
    fireEvent.click(screen.getByTestId('channel-option-telegram'))
    expect(await screen.findByTestId('channel-link-state')).toBeTruthy()
    expect(screen.getByTestId('channel-link-state').textContent).toBe('Not linked yet: open Chhatri in Telegram and press Start.')
    expect(screen.getByText('Telegram is simulated here: messages show on the console phone.')).toBeTruthy()
    await waitFor(() => expect(kit.backend.runtime.preferred.get('S-0142')).toBe('telegram'))
  })

  it('is not there while the flag is off', async () => {
    await openSettings('n1_miniapp')
    expect(screen.queryByTestId('channel-choice')).toBeNull()
  })
})
