/** Mock GET /api/merchants/{id}/cover: DEMO.md numbers, the derived status of fs-07 section 5.3 and the strict parser. */
import { afterEach, describe, expect, it } from 'vitest'

import { parseCover } from '../../miniapp/api/parse'
import type { MockBackend } from '../backend'
import { MOCK_OFFICER_TOKEN } from '../fixtures'
import { testApi } from '../testkit'
import { coverStatusText, deriveCover, type StoredCover } from './cover'

let backend: MockBackend
afterEach(() => backend?.dispose())

async function session(scenario: 'monsoon' | 'buy_cover', at: string) {
  const kit = testApi()
  backend = kit.backend
  kit.client.setOfficerToken(MOCK_OFFICER_TOKEN)
  await kit.api.load(scenario)
  await kit.api.seek(at)
  return kit
}

const BOUGHT: StoredCover = {
  id: 'CV-S-0907-20250825',
  merchant_id: 'S-0907',
  purchased_at: '2025-08-18T18:00:00+05:30',
  starts_on: '2025-08-25',
  premium_per_day_paise: 1416,
  prepaid_through: '2025-09-23',
}

describe('GET /api/merchants/{id}/cover', () => {
  it('shows Anil at 17:05: active, the Z7 price, the alert in force and the paid claim', async () => {
    const { api } = await session('monsoon', '17:05')
    const cover = await api.cover('S-0142')
    expect(cover).toEqual({
      merchant_id: 'S-0142',
      cover_id: 'CV-0142',
      status: 'ACTIVE',
      status_text_hi: 'आपका कवर चालू है। प्रीमियम 22 अगस्त तक जमा है।',
      status_text_en: 'Your cover is active. Premium is paid through 22 August.',
      zone_id: 'Z7',
      zone_name: 'Parel · Lalbaug',
      purchased_at: '2025-03-10T11:00:00+05:30',
      starts_on: '2025-03-17',
      prepaid_through: '2025-08-22',
      waiting_period_days: 7,
      premium_per_day_paise: 1862,
      premium_per_day_label: '₹18.62',
      premium_due: false,
      annual_limit_paise: 3_000_000,
      annual_limit_label: '₹30,000',
      amount_claimed_paise: 138_000,
      amount_claimed_label: '₹1,380',
      amount_remaining_paise: 2_862_000,
      amount_remaining_label: '₹28,620',
      alert_active: true,
      alert_id: 'A-20250818-01',
    })
    expect(parseCover(cover)).toEqual(cover)
  })

  it('counts a payout only once it is credited, and the alert only while it is valid', async () => {
    const { api } = await session('monsoon', '17:03')
    expect(await api.cover('S-0142')).toMatchObject({ amount_claimed_label: '₹0', amount_remaining_label: '₹30,000', alert_active: true })
    await api.seek('17:04')
    expect(await api.cover('S-0142')).toMatchObject({ amount_claimed_label: '₹1,380' })
    const { api: morning } = await session('monsoon', '09:00')
    expect(await morning.cover('S-0142')).toMatchObject({ alert_active: false, alert_id: null, amount_claimed_paise: 0 })
  })

  it('gives Ramesh status NONE, the price his zone would pay, and nulls', async () => {
    const { api } = await session('buy_cover', '18:00')
    const cover = await api.cover('S-0907')
    expect(cover).toEqual({
      merchant_id: 'S-0907',
      cover_id: null,
      status: 'NONE',
      status_text_hi: 'अभी कवर नहीं है',
      status_text_en: 'No cover yet',
      zone_id: 'Z3',
      zone_name: 'Worli · Lower Parel',
      purchased_at: null,
      starts_on: null,
      prepaid_through: null,
      waiting_period_days: 7,
      premium_per_day_paise: 1416,
      premium_per_day_label: '₹14.16',
      premium_due: false,
      annual_limit_paise: null,
      annual_limit_label: null,
      amount_claimed_paise: null,
      amount_claimed_label: null,
      amount_remaining_paise: null,
      amount_remaining_label: null,
      alert_active: false,
      alert_id: null,
    })
    expect(parseCover(cover)).toEqual(cover)
  })

  it('shows Ramesh as WAITING until 25 August once the premium is paid', async () => {
    const { api } = await session('buy_cover', '18:00')
    await api.paytmWebhook((await api.premiumLink('S-0907')).premium?.link_id ?? '')
    const cover = await api.cover('S-0907')
    expect(cover).toMatchObject({
      status: 'WAITING',
      status_text_en: 'Your cover starts on 25 August.',
      status_text_hi: 'आपका कवर 25 अगस्त से शुरू होगा।',
      amount_claimed_label: '₹0',
      amount_remaining_label: '₹30,000',
      premium_due: false,
    })
    expect(parseCover(cover)).toEqual(cover)
  })

  it('answers 404 for a merchant that is not in the city', async () => {
    const { api } = await session('monsoon', '17:05')
    await expect(api.cover('S-9999')).rejects.toMatchObject({ code: 'not_found', status: 404, message: 'merchant S-9999 not found' })
  })
})

describe('derived cover status', () => {
  it('is WAITING before starts_on and ACTIVE from the day it starts', () => {
    expect(deriveCover(BOUGHT, '2025-08-24')).toEqual({ status: 'WAITING', premium_due: false })
    expect(deriveCover(BOUGHT, '2025-08-25')).toEqual({ status: 'ACTIVE', premium_due: false })
  })

  it('asks for the next premium once the prepaid days are over (fs-07 AC-K6-05)', () => {
    expect(deriveCover(BOUGHT, '2025-09-23')).toEqual({ status: 'ACTIVE', premium_due: false })
    expect(deriveCover(BOUGHT, '2025-09-24')).toEqual({ status: 'ACTIVE', premium_due: true })
    expect(deriveCover({ ...BOUGHT, prepaid_through: null }, '2025-08-25')).toEqual({ status: 'ACTIVE', premium_due: true })
  })

  it('is NONE without a cover record', () => {
    expect(deriveCover(null, '2025-08-25')).toEqual({ status: 'NONE', premium_due: false })
  })

  it('picks the catalogue sentence for the state', () => {
    expect(coverStatusText('WAITING', false, BOUGHT)).toEqual({ en: 'Your cover starts on 25 August.', hi: 'आपका कवर 25 अगस्त से शुरू होगा।' })
    expect(coverStatusText('ACTIVE', true, BOUGHT).en).toBe("Your cover is active, but the premium for the coming days hasn't been paid yet.")
    expect(coverStatusText('ACTIVE', false, BOUGHT).en).toBe('Your cover is active. Premium is paid through 23 September.')
    expect(coverStatusText('NONE', false, null)).toEqual({ en: 'No cover yet', hi: 'अभी कवर नहीं है' })
  })
})
