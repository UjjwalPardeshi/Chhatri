/**
 * KPI tiles (SPEC §17.2, deck slide 6): zones triggered, shops paid, trigger to money, as one
 * 64 px strip of three cells (value and label on one baseline) so the live panel keeps room for
 * the event feed. When a number changes live (17:00 trigger, 17:04 credit) it counts up over
 * 500 ms and its cell flashes.
 */
import type { Kpis } from '../../api/types'
import { useChangedKeys, useCountUp } from '../../state/motion'

/** The three deck tiles; the totals only feed hover titles when known. */
export type KpiFigures = Pick<Kpis, 'zones_triggered' | 'shops_paid' | 'trigger_to_money_min'> & Partial<Pick<Kpis, 'total_paid_label' | 'instalments_paused'>>

export function triggerToMoney(kpis: KpiFigures): string {
  return kpis.trigger_to_money_min === null ? '—' : `${kpis.trigger_to_money_min} min`
}

function Counted({ value }: { value: number }) {
  return <>{useCountUp(value).toLocaleString('en-IN')}</>
}

/** "4 min" as a big number with a quiet unit: at the presenter's 44 px the whole of "4 min" would not fit its cell. */
function Minutes({ minutes }: { minutes: number | null }) {
  if (minutes === null) return <>—</>
  return (
    <>
      {minutes}
      <span className="kpi__unit"> min</span>
    </>
  )
}

export function KpiTiles({ kpis }: { kpis: KpiFigures }) {
  const tiles = [
    { key: 'zones', value: <Counted value={kpis.zones_triggered} />, raw: String(kpis.zones_triggered), caption: 'zones triggered', title: null },
    {
      key: 'shops',
      value: <Counted value={kpis.shops_paid} />,
      raw: String(kpis.shops_paid),
      caption: 'shops paid',
      title: kpis.total_paid_label ? `${kpis.total_paid_label} paid in total` : null,
    },
    {
      key: 'ttm',
      value: <Minutes minutes={kpis.trigger_to_money_min} />,
      raw: triggerToMoney(kpis),
      caption: 'trigger to money',
      title: kpis.instalments_paused === undefined ? null : `${kpis.instalments_paused} loan instalments paused`,
    },
  ]
  const changed = useChangedKeys(Object.fromEntries(tiles.map((t) => [t.key, t.raw])))
  return (
    <section className="card kpis" aria-label="Key numbers">
      {tiles.map((tile) => (
        <div key={tile.key} className={`kpi ${changed.has(tile.key) ? 'is-changed' : ''}`} data-kpi={tile.key} title={tile.title ?? undefined}>
          <span className="kpi__value num">{tile.value}</span>
          <span className="kpi__caption">{tile.caption}</span>
        </div>
      ))}
    </section>
  )
}
