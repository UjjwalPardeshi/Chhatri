import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { ChannelView } from '../../api/types'
import { telegramOf, type ChannelState } from '../../state/useChannel'
import { ChannelSwitch, channelLine } from './ChannelSwitch'
import { Phone } from './Phone'

const VIEW: ChannelView = {
  merchant_id: 'S-0142',
  preferred_channel: 'telegram',
  channels: [
    { channel: 'whatsapp', mode: 'SIMULATED' },
    { channel: 'telegram', mode: 'LIVE', linked: true, bot_username: 'chaatri_paytm_bot', deep_link: 'https://t.me/chaatri_paytm_bot?start=S-0142' },
  ],
}

function state(over: Partial<ChannelState> = {}): ChannelState {
  return { on: true, view: VIEW, telegram: telegramOf(VIEW), preferred: VIEW.preferred_channel, busy: false, error: null, choose: vi.fn<ChannelState['choose']>(async () => undefined), ...over }
}

describe('ChannelSwitch (telegram_channel)', () => {
  it('renders nothing while the flag is off', () => {
    const { container } = render(<ChannelSwitch state={state({ on: false })} />)
    expect(container.innerHTML).toBe('')
  })

  it('shows the chosen app with its mode, the link state and the bot deep link', () => {
    render(<ChannelSwitch state={state()} />)
    expect(screen.getByRole('button', { name: 'Telegram' }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByTestId('channel-line').textContent).toContain('Telegram · LIVE · chat linked')
    expect(screen.getByRole('link', { name: 'Open @chaatri_paytm_bot' }).getAttribute('href')).toBe('https://t.me/chaatri_paytm_bot?start=S-0142')
  })

  it('switches back to WhatsApp on a tap, and a tap on the current app does nothing', () => {
    const choose = vi.fn<ChannelState['choose']>(async () => undefined)
    render(<ChannelSwitch state={state({ choose })} />)
    fireEvent.click(screen.getByRole('button', { name: 'Telegram' }))
    fireEvent.click(screen.getByRole('button', { name: 'WhatsApp' }))
    expect(choose).toHaveBeenCalledTimes(1)
    expect(choose).toHaveBeenCalledWith('whatsapp')
  })

  it('reads WhatsApp with its mode, and an unlinked Telegram says so', () => {
    expect(channelLine({ view: VIEW, telegram: telegramOf(VIEW), preferred: 'whatsapp' })).toBe('WhatsApp · SIMULATED')
    const unlinked = { ...VIEW, channels: [VIEW.channels[0], { ...VIEW.channels[1], linked: false }] } as ChannelView
    expect(channelLine({ view: unlinked, telegram: telegramOf(unlinked), preferred: 'telegram' })).toBe('Telegram · LIVE · no chat linked yet')
  })

  it('dresses the phone as the Telegram bot', () => {
    render(<Phone now="2025-08-19T17:05:00+05:30" messages={[]} footer={null} status={null} channel="telegram" />)
    expect(screen.getByTestId('phone').className).toContain('phone--telegram')
    expect(screen.getByText('Chhatri bot')).toBeTruthy()
  })
})
