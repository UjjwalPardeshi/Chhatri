/**
 * The storm example (deck slide 6, SPEC §17.2 golden strings) on a navy band: the static 17:05
 * map on the left, the zone card, KPI tiles and "Why Zone 9 got nothing" exactly as the live panel
 * shows them at 17:05 on the right, and two ways into the live replay under the map.
 */
import { STORM } from '../../content/deck'
import type { LaunchState } from '../../state/useLaunch'
import { Explanations } from '../panel/Explanations'
import { KpiTiles } from '../panel/KpiTiles'
import { ZoneCard, type ZoneCardData } from '../panel/ZoneCard'
import { nextHour, type ZoneTrend } from '../panel/zoneTrend'
import { STORM_MAP, StormMap } from '../storm/StormMap'
import { LaunchButton } from './LaunchButton'
import { LaunchError } from './LaunchError'
import { RevealSection } from './Reveal'

export const STORM_PANEL: ZoneCardData = {
  zone: { zone_id: STORM.zone.id, status: 'triggered', shops: STORM.zone.shops, ward: STORM.zone.ward, name: STORM.zone.name },
  rows: STORM.rows.map((r) => ({ label: r.label, value: r.value })),
}

/** Trigger window hours of the monsoon replay (14:00 to 17:00, SPEC §17.2). */
const WINDOW_HOURS = ['14:00', '15:00', '16:00'] as const
/** Z7's golden 3-hour index (SPEC §17.2). */
const Z7_INDEX_PCT = 37

export const STORM_TREND: ZoneTrend = {
  pct: Z7_INDEX_PCT,
  hours: (STORM_MAP.hourly[STORM.zone.id] ?? []).map((pct, i) => ({ label: WINDOW_HOURS[i] ?? '', pct })),
  window: `${WINDOW_HOURS[0]} to ${nextHour(WINDOW_HOURS[WINDOW_HOURS.length - 1])}`,
}

const MAP_CHIP = 'Mumbai · monsoon replay · 17:05 · simulated'
const STORM_KEYS = ['storm-live', 'storm-jump'] as const

export function Storm({ launcher }: { launcher: LaunchState }) {
  return (
    <RevealSection label="The storm replay" id="ov-storm" className="ov-storm" tone="navy">
      <h2 className="ov-h2">The claims team sees the loss as it happens.</h2>
      <div className="ov-storm__grid">
        <div className="ov-storm__map">
          <StormMap when={MAP_CHIP} />
          <div className="ov-storm__ctas">
            <LaunchButton launcher={launcher} id="storm-live" target="stormLive" label="Watch 17:00 to 17:05 live" busyLabel="Loading the storm…" />
            <LaunchButton launcher={launcher} id="storm-jump" target="storm" tone="link" label="Jump to 17:05" />
          </div>
          <LaunchError launcher={launcher} keys={STORM_KEYS} />
        </div>
        <div className="ov-storm__panel">
          <ZoneCard panel={STORM_PANEL} trend={STORM_TREND} />
          <KpiTiles kpis={{ zones_triggered: STORM.zonesTriggered, shops_paid: STORM.shopsPaid, trigger_to_money_min: STORM.triggerToMoneyMin }} />
          <Explanations explanations={{ Z9: STORM.z9 }} />
        </div>
      </div>
    </RevealSection>
  )
}
