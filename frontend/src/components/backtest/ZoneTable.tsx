/**
 * Premiums against payouts per zone (SPEC §18 per-zone loss ratios, §9.7 pricing): each loss
 * ratio as a bar on a shared scale with a line at the ratio premiums are priced for (1 − the
 * published loading, from GET /api/policy). Bars past the line paid out more than priced for.
 * Every bar carries its sums as a tooltip.
 */
import type { BacktestZone } from '../../api/types'
import { formatInr } from '../../lib/money'
import { pctLabel } from '../proof/ProofBars'

const PCT = 100
/** The bar scale runs a little past the largest value (or the priced-for line) so neither touches the end. */
const HEADROOM = 1.15

function ratioTitle(zone: BacktestZone, target: number | null): string {
  const priced = target === null ? '' : ` · priced for ${pctLabel(target)}`
  return `${zone.zone_id}: payouts ${formatInr(zone.payouts_paise)} of premiums ${formatInr(zone.premiums_paise)} = ${pctLabel(zone.loss_ratio)}${priced}`
}

function RatioBar({ zone, scale, target }: { zone: BacktestZone; scale: number; target: number | null }) {
  const over = target !== null && zone.loss_ratio > target
  return (
    <span className={`ratio ${over ? 'ratio--over' : ''}`} title={ratioTitle(zone, target)}>
      <span className="ratio__plot">
        <span className="ratio__bar" style={{ width: `${(zone.loss_ratio / scale) * PCT}%` }} />
        {target !== null ? <span className="ratio__target" style={{ left: `${(target / scale) * PCT}%` }} /> : null}
      </span>
      <span className="ratio__value num">{pctLabel(zone.loss_ratio)}</span>
    </span>
  )
}

type Props = { zones: readonly BacktestZone[]; target: number | null }

export function ZoneTable({ zones, target }: Props) {
  const scale = Math.max(target ?? 0, ...zones.map((z) => z.loss_ratio)) * HEADROOM || 1
  const anyOver = target !== null && zones.some((z) => z.loss_ratio > target)
  return (
    <>
      <table className="table zones-table">
        <thead>
          <tr>
            <th>Zone</th>
            <th className="num">Premium / day</th>
            <th className="num">Premiums</th>
            <th className="num">Payouts</th>
            <th>Loss ratio</th>
            <th className="num">False +</th>
            <th className="num">Missed</th>
          </tr>
        </thead>
        <tbody>
          {zones.map((z) => (
            <tr key={z.zone_id}>
              <td>{z.zone_id}</td>
              <td className="num">{z.premium_per_day_label}</td>
              <td className="num">{formatInr(z.premiums_paise)}</td>
              <td className="num">{formatInr(z.payouts_paise)}</td>
              <td aria-label={`Loss ratio ${pctLabel(z.loss_ratio)}`}>
                <RatioBar zone={z} scale={scale} target={target} />
              </td>
              <td className="num">{z.chhatri_fp}</td>
              <td className="num">{z.chhatri_fn}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {target !== null ? (
        <p className="ratio-legend muted">
          <span className="ratio-legend__line" aria-hidden="true" /> Premiums are priced for a {pctLabel(target)} loss ratio.{anyOver ? ' Amber bars paid out more than that.' : ''}
        </p>
      ) : null}
    </>
  )
}
