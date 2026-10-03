/**
 * What the levers cost and pay (GET /api/pricing): for the chosen zone the premium per day, month and year, the
 * expected payout per shop, the payout days and today's premium with the loss ratio it would run at; then the city's
 * spread of premiums and the trigger's quality at the floor priced. Every figure is the server's; a zone with no
 * premium today reads "not priced today".
 */
import { useId } from 'react'

import type { Pricing, PricingZone } from '../../api/pricing'
import { formatInr } from '../../lib/money'
import { pctLabel } from '../proof/ProofBars'
import { falsePayoutLine, NOT_PRICED_TODAY, paysOutMore, percent, recallLine, zoneOf } from './pricingModel'

type Props = { answer: Pricing; zoneId: string; onZone: (zoneId: string) => void }

function Figure({ label, value, lead = false, note }: { label: string; value: string; lead?: boolean; note?: string }) {
  return (
    <div className={lead ? 'pricing-figure pricing-figure--lead' : 'pricing-figure'}>
      <dt>{label}</dt>
      <dd className="num">{value}</dd>
      {note ? <dd className="pricing-figure__note">{note}</dd> : null}
    </div>
  )
}

function ZoneFigures({ zone }: { zone: PricingZone }) {
  const today = zone.current_premium_per_day_paise
  const ratio = zone.loss_ratio_at_current_price
  return (
    <dl className="pricing-figures" data-testid="pricing-zone">
      <Figure lead label="Premium per day" value={formatInr(zone.premium_per_day_paise)} />
      <Figure label="Premium per month" value={formatInr(zone.premium_per_month_paise)} />
      <Figure label="Premium per year" value={formatInr(zone.premium_per_year_paise)} />
      <Figure label="Expected payout per shop" value={`${formatInr(zone.expected_payout_per_year_paise)} a year`} />
      <Figure label="Payout days" value={`${zone.payout_days_per_year} a year`} />
      <Figure label="Covered shops" value={String(zone.shops)} />
      <Figure label="Today's premium" value={today === null ? NOT_PRICED_TODAY : `${formatInr(today)} a day`} />
      <Figure label="Loss ratio at today's price" value={ratio === null ? NOT_PRICED_TODAY : pctLabel(ratio)} note={paysOutMore(zone) ? 'pays out more than it collects' : undefined} />
    </dl>
  )
}

function CityLine({ answer }: { answer: Pricing }) {
  const { city } = answer
  return (
    <dl className="pricing-city" data-testid="pricing-city">
      <div>
        <dt>Across the city</dt>
        <dd className="num">
          Premium per day {formatInr(city.premium_min_paise)} lowest · {formatInr(city.premium_median_paise)} median · {formatInr(city.premium_max_paise)} highest
        </dd>
      </div>
      <div>
        <dt>At a {percent(answer.levers.floor_pct)} floor</dt>
        <dd className="num">
          {recallLine(city)} · {falsePayoutLine(city)}
        </dd>
      </div>
    </dl>
  )
}

export function PricingResults({ answer, zoneId, onZone }: Props) {
  const id = useId()
  const zone = zoneOf(answer, zoneId)
  return (
    <div className="pricing-results">
      <div className="pricing-zone">
        <label htmlFor={id}>Zone</label>
        <select id={id} className="input" value={zone.zone_id} onChange={(e) => onZone(e.target.value)}>
          {answer.zones.map((z) => (
            <option key={z.zone_id} value={z.zone_id}>{`${z.zone_id} · ${z.name}`}</option>
          ))}
        </select>
      </div>
      <ZoneFigures zone={zone} />
      <CityLine answer={answer} />
    </div>
  )
}
