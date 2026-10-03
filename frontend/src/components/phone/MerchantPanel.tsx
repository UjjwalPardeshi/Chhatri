/**
 * Merchant context beside the phone (SPEC §20 "Merchant phone"): the Soundbox and the money side
 * by side (payouts with the decision formula, §4.3 published numbers, or for a cover bought after
 * an alert the BLOCKED result with its start date, §13.6), the "What happened" stepper, then the
 * shop's file across the full width: cover, the Chhatri rider premium, loan and expected day. The
 * presenter's script stays folded away at the bottom unless asked for (presenter mode, `?presenter=1`).
 */
import { useState, type ReactNode } from 'react'

import type { MerchantDetail, ScenarioName } from '../../api/types'
import { dayLabel, hhmm } from '../../lib/time'
import { actorLabel } from '../../lib/actors'
import { usePresenter } from '../../state/presenter'
import { Icon } from '../common/Icon'
import type { CoverOffer } from './coverOffer'
import type { HappenedStep } from './whatHappened'
import { WhatHappened } from './WhatHappened'

export const PRESENTER_STEPS: Readonly<Record<ScenarioName, readonly string[]>> = Object.freeze({
  monsoon: [
    'Play or seek to 17:05: triggers at 17:00, ₹1,380 credited at 17:04, instalment paused at 17:05.',
    'Tap “मुझे इतने ही पैसे क्यों मिले?”: Chhatri answers with ₹4,380 and 63%.',
    'Tap “मेरा नुकसान ज़्यादा हुआ।”: a claims officer gets case C-2291.',
  ],
  illness: [
    'Seek to 11:20: Chhatri checks in because the shop was silent all Wednesday.',
    'Tap the voice reply “मैं अस्पताल में हूँ, बुखार है।”.',
    'Send Anil’s admission slip, then step +5 min: ₹1,500 is paid, instalment paused.',
  ],
  illness_mismatch: [
    'Seek to 11:20 and tap the voice reply.',
    'Send the slip with a different name: no automatic payout, it goes to a human.',
    'Open Claims and approve the case: ₹1,500 is paid after the officer decides.',
  ],
  buy_cover: ['Tap “Red alert tomorrow. Cover me today.”: BLOCKED, cover starts after the waiting period, with a Paytm link.'],
})

function Row({ label, value, wide = false }: { label: string; value: string; wide?: boolean }) {
  return (
    <div className={wide ? 'kv kv--wide' : 'kv'}>
      <dt>{label}</dt>
      <dd className="num">{value}</dd>
    </div>
  )
}

function Blocked({ offer }: { offer: CoverOffer }) {
  return (
    <div className="blocked" data-testid="cover-blocked">
      <div className="blocked__head">
        <span className="badge badge--solid-red">Blocked</span>
        <strong>Cover bought after an alert</strong>
      </div>
      <p className="blocked__text">
        New cover starts after the waiting period{offer.startsOn ? <>: cover starts <strong className="num">{offer.startsOn}</strong></> : null}. It won’t apply to
        tomorrow’s alert.
      </p>
      {offer.link ? <p className="muted num">Paytm link sent for {offer.link.firstPayment} ({offer.link.perDay} a day)</p> : null}
    </div>
  )
}

function Money({ merchant, offer }: { merchant: MerchantDetail; offer: CoverOffer | null }) {
  const latest = merchant.decisions.at(-1) ?? null
  return (
    <section className="card merchant-card" aria-label="Money">
      <p className="eyebrow">Money</p>
      {offer ? <Blocked offer={offer} /> : null}
      {merchant.payouts.length === 0 && !offer ? <p className="muted">No payouts yet.</p> : null}
      <ul className="money-list">
        {merchant.payouts.map((p) => (
          <li key={p.id}>
            <strong className="num">{p.amount_label}</strong>
            <span className={`badge ${p.status === 'CREDITED' ? 'badge--green' : 'badge--amber'}`}>{p.status}</span>
            <span className="muted num">{p.credited_at ? `credited ${hhmm(p.credited_at)}` : `created ${hhmm(p.created_at)}`}</span>
          </li>
        ))}
      </ul>
      {latest?.explanation ? (
        <div className="formula">
          <p className="formula__en num">{latest.explanation.formula_en}</p>
          <p className="formula__hi hi num" lang="hi">
            {latest.explanation.formula_hi}
          </p>
          <p className="muted">
            {latest.id} · {latest.outcome} by {actorLabel(latest.decided_by)} · rules {latest.rules_version}
          </p>
        </div>
      ) : null}
    </section>
  )
}

function PresenterNotes({ scenario }: { scenario: ScenarioName }) {
  const presenter = usePresenter()
  const [open, setOpen] = useState(presenter.on)
  return (
    <div className="presenter">
      <button type="button" className="presenter__toggle" aria-expanded={open} aria-controls="presenter-notes" onClick={() => setOpen((v) => !v)}>
        <Icon name="notes" size={14} />
        {open ? 'Hide presenter notes' : 'Presenter notes'}
      </button>
      {open ? (
        <ol id="presenter-notes" className="card merchant-card presenter__list">
          {PRESENTER_STEPS[scenario].map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      ) : null}
    </div>
  )
}

function MerchantFile({ merchant }: { merchant: MerchantDetail }) {
  return (
    <section className="card merchant-card merchant-file">
      <p className="eyebrow">Merchant</p>
      <h2>{merchant.shop_name}</h2>
      <p className="muted">
        {merchant.owner_name} ·{' '}
        <span className="hi" lang="hi">
          {merchant.owner_name_hi}
        </span>{' '}
        · {merchant.id} · Zone {merchant.zone_id.replace(/^Z/, '')}
      </p>
      <dl className="kv-list">
        <Row label="Cover" value={merchant.cover ? `${merchant.cover.status} · prepaid through ${dayLabel(merchant.cover.prepaid_through)}` : 'Not covered'} wide />
        <Row label="Loan instalment" value={merchant.loan ? `${merchant.loan.daily_instalment_label} a day · ${merchant.loan.lender_name}` : 'No loan'} wide />
        {merchant.cover ? <Row label="Chhatri rider premium" value={`${merchant.cover.premium_per_day_label} a day`} /> : null}
        <Row label="Expected today" value={merchant.expected_today_label ?? '—'} />
        <Row label="KYC name" value={merchant.kyc_name_masked} />
        <Row label="Phone" value={merchant.phone_masked} />
      </dl>
    </section>
  )
}

type Props = { merchant: MerchantDetail; scenario: ScenarioName | null; soundbox?: ReactNode; offer?: CoverOffer | null; steps?: readonly HappenedStep[]; channel?: ReactNode }

export function MerchantPanel({ merchant, scenario, soundbox = null, offer = null, steps = [], channel = null }: Props) {
  return (
    <aside className="merchant-panel">
      <div className="merchant-panel__soundbox">{soundbox}</div>
      {channel}
      <Money merchant={merchant} offer={offer} />
      <WhatHappened steps={steps} />
      <MerchantFile merchant={merchant} />
      {scenario ? <PresenterNotes scenario={scenario} /> : null}
    </aside>
  )
}
