/** Merchant context beside the phone: cover, loan, expected day, payouts and decision formulas. */
import type { MerchantDetail, ScenarioName } from '../../api/types'
import { dayLabel, hhmm } from '../../lib/time'

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

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="kv">
      <dt>{label}</dt>
      <dd className="num">{value}</dd>
    </div>
  )
}

export function MerchantPanel({ merchant, scenario }: { merchant: MerchantDetail; scenario: ScenarioName | null }) {
  const latest = merchant.decisions.at(-1) ?? null
  return (
    <aside className="merchant-panel">
      <section className="card merchant-card">
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
          <Row label="Cover" value={merchant.cover ? `${merchant.cover.status} · prepaid through ${dayLabel(merchant.cover.prepaid_through)}` : 'Not covered'} />
          {merchant.cover ? <Row label="Premium" value={`${merchant.cover.premium_per_day_label} a day`} /> : null}
          <Row label="Loan instalment" value={merchant.loan ? `${merchant.loan.daily_instalment_label} a day · ${merchant.loan.lender_name}` : 'No loan'} />
          <Row label="Expected today" value={merchant.expected_today_label ?? '—'} />
          <Row label="KYC name" value={merchant.kyc_name_masked} />
          <Row label="Phone" value={merchant.phone_masked} />
        </dl>
      </section>
      <section className="card merchant-card">
        <p className="eyebrow">Money</p>
        {merchant.payouts.length === 0 ? <p className="muted">No payouts yet.</p> : null}
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
              {latest.id} · {latest.outcome} by {latest.decided_by} · rules {latest.rules_version}
            </p>
          </div>
        ) : null}
      </section>
      {scenario ? (
        <section className="card merchant-card presenter">
          <p className="eyebrow">Demo script</p>
          <ol>
            {PRESENTER_STEPS[scenario].map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </section>
      ) : null}
    </aside>
  )
}
