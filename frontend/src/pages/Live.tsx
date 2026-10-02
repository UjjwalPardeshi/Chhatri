/**
 * Live map page "/live" (SPEC §20, deck slide 6): the city heat map on the left; on the right the
 * zone card (with its 3-hour headline), KPI tiles, "Why Zone 9 got nothing" (only once the 17:00
 * evaluation has paid other zones; a neutral note before) and the live event feed. The demo
 * merchant's credit at 17:04 raises a toast over the map. While a load, seek or reset rebuilds the
 * replay (1-3 s), a veil says so, so the old frame never reads as the new time.
 */
import { useCallback, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router'

import type { StateSnapshot } from '../api/types'
import { Feature } from '../components/common/Feature'
import { OpsStrip } from '../components/layout/OpsStrip'
import { LiveMap } from '../components/map/LiveMap'
import { EventFeed } from '../components/panel/EventFeed'
import { ZoneExplanations } from '../components/panel/Explanations'
import { KpiTiles } from '../components/panel/KpiTiles'
import { MomentCard, type MomentOps } from '../components/panel/MomentCard'
import { PayoutToast } from '../components/panel/PayoutToast'
import { WhatIfDrawer } from '../components/panel/WhatIf'
import { ZoneCard } from '../components/panel/ZoneCard'
import { liveNow, zoneTrend } from '../components/panel/zoneTrend'
import { AsyncView, ErrorState, Loading } from '../components/common/Status'
import { isFeatureEnabled } from '../features'
import { railDelayMinutes, triggerRule, type TriggerRule } from '../lib/rules'
import { useLive, type ReplayAction } from '../state/live'
import { useOps } from '../state/ops'
import { useWhatIfToggle } from '../state/whatIfToggle'
import { useAsync } from '../state/useAsync'
import { useGeo } from '../state/useGeo'
import { useMerchant } from '../state/useMerchant'

/** Default card: the demo merchant's zone if it triggered, else the first trigger, else that zone. */
export function defaultZone(snapshot: StateSnapshot, merchantZone: string | null): string | null {
  const triggered = snapshot.triggers.map((t) => t.zone_id)
  if (merchantZone && triggered.includes(merchantZone)) return merchantZone
  if (triggered.length > 0) return triggered[0]
  return merchantZone ?? snapshot.zones[0]?.zone_id ?? null
}

function ZonePanelCard({ zoneId, snapshot, rule, action = null }: { zoneId: string; snapshot: StateSnapshot; rule: TriggerRule | null; action?: ReactNode }) {
  const { api } = useLive()
  const zone = snapshot.zones.find((z) => z.zone_id === zoneId)
  const key = `${JSON.stringify(zone)}|${JSON.stringify(snapshot.kpis)}|${snapshot.triggers.length}`
  const panel = useAsync((signal) => api.zonePanel(zoneId, signal), [api, zoneId, key])
  return (
    <AsyncView {...panel} label="Loading zone…">
      {(data) => {
        const trend = zoneTrend(data, snapshot.triggers)
        return <ZoneCard key={data.zone.zone_id} panel={data} trend={trend} live={liveNow(data.zone, trend)} floorPct={rule?.floorPct ?? null} action={action} />
      }}
    </AsyncView>
  )
}

/** The veil's words for a replay action that rebuilds the city (null for quick ones). */
export function rebuildLabel(action: ReplayAction | null): string | null {
  if (action === 'load') return 'Loading the replay…'
  if (action === 'seek' || action === 'reset') return 'Moving the replay clock…'
  return null
}

/** The H8 numbers the moment card words once they exist (card 6.2): payouts in flight and the holiday requests. */
export function momentOps(summary: ReturnType<typeof useOps>['summary']): MomentOps | null {
  if (!summary) return null
  const pending = summary.payouts_today.pending_count
  return { pendingPayouts: pending > 0 ? pending : null, holidayRequests: summary.holiday_requests_today }
}

export default function Live() {
  const { api, snapshot, snapshotError, refresh, replayBusy } = useLive()
  const rebuilding = rebuildLabel(replayBusy)
  const navigate = useNavigate()
  const geo = useGeo(api)
  const merchant = useMerchant(snapshot?.demo_merchant_id ?? null)
  /** The trigger rule the legend and the sparkline draw (fs-08 13.2): read from the published rules, never copied. */
  const policy = useAsync((signal) => api.policy(signal), [api])
  const rule = triggerRule(policy.data?.rules)
  const ops = useOps()
  const whatIfOn = isFeatureEnabled('h24_whatif')
  const [whatIfOpen, setWhatIfOpen] = useState(false)
  const toggleWhatIf = useCallback(() => setWhatIfOpen((open) => !open), [])
  useWhatIfToggle(toggleWhatIf, whatIfOn)
  const scenarioKey = `${snapshot?.clock.scenario}|${snapshot?.clock.start}`
  /** A picked zone belongs to one scenario run; a new run falls back to the default zone. */
  const [picked, setPicked] = useState<{ run: string; zone: string } | null>(null)
  const chosen = picked?.run === scenarioKey ? picked.zone : null

  if (!snapshot) {
    return snapshotError ? <ErrorState error={snapshotError} title="Cannot reach the replay" onRetry={refresh} /> : <Loading label="Loading the city…" />
  }
  const zoneId = chosen ?? defaultZone(snapshot, merchant.data?.zone_id ?? null)
  /** The demo merchant prices the example line when it is covered in the zone on the card (else the server would say 422). */
  const exampleMerchant = merchant.data?.covered && merchant.data.zone_id === zoneId ? merchant.data.id : null

  return (
    <div className="home">
      <Feature name="h8_ops_strip">
        {/* Design system open question 3: the ops strip is a band over the map column, so the panel keeps the Z9 note in view. */}
        <div className="home__strip">
          <OpsStrip />
        </div>
      </Feature>
      <div className="home__map">
        <AsyncView {...geo} label="Loading wards and hexes…">
          {(data) => (
            <LiveMap
              geo={data}
              snapshot={snapshot}
              merchant={merchant.data}
              selected={zoneId}
              rule={rule}
              onSelectZone={(zone) => setPicked({ run: scenarioKey, zone })}
              onOpenMerchant={(id) => navigate(`/merchant/${id}`)}
            />
          )}
        </AsyncView>
        <PayoutToast merchantId={snapshot.demo_merchant_id} shopName={merchant.data?.shop_name ?? null} />
        {rebuilding ? (
          <output className="map-veil" aria-live="polite">
            <span className="spinner" />
            {rebuilding}
          </output>
        ) : null}
      </div>
      <aside className="home__panel" data-whatif={whatIfOn && whatIfOpen ? 'open' : undefined}>
        <Feature name="console_polish">
          <MomentCard clock={snapshot.clock} zones={snapshot.zones} triggers={snapshot.triggers} kpis={snapshot.kpis} railDelayMinutes={railDelayMinutes(policy.data?.rules)} pausing={replayBusy === 'pause'} ops={momentOps(ops.summary)} />
        </Feature>
        {zoneId ? (
          <ZonePanelCard
            zoneId={zoneId}
            snapshot={snapshot}
            rule={rule}
            action={
              whatIfOn ? (
                <button type="button" className="btn whatif-open" aria-expanded={whatIfOpen} onClick={toggleWhatIf}>
                  What if…
                </button>
              ) : null
            }
          />
        ) : null}
        {whatIfOn && zoneId && whatIfOpen ? <WhatIfDrawer key={`${scenarioKey}|${zoneId}`} zoneId={zoneId} maxShops={snapshot.zones.find((z) => z.zone_id === zoneId)?.shops ?? 0} exampleMerchantId={exampleMerchant} onClose={() => setWhatIfOpen(false)} /> : null}
        <KpiTiles kpis={snapshot.kpis} />
        <ZoneExplanations snapshot={snapshot} />
        <EventFeed items={snapshot.feed} floorPct={rule?.floorPct} />
      </aside>
    </div>
  )
}
