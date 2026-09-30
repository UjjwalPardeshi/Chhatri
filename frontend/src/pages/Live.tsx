/**
 * Live map page "/live" (SPEC §20, deck slide 6): the city heat map on the left; on the right the
 * zone card (with its 3-hour headline), KPI tiles, "Why Zone 9 got nothing" (only once the 17:00
 * evaluation has paid other zones; a neutral note before) and the live event feed. The demo
 * merchant's credit at 17:04 raises a toast over the map. While a load, seek or reset rebuilds the
 * replay (1-3 s), a veil says so, so the old frame never reads as the new time.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router'

import type { StateSnapshot } from '../api/types'
import { LiveMap } from '../components/map/LiveMap'
import { EventFeed } from '../components/panel/EventFeed'
import { ZoneExplanations } from '../components/panel/Explanations'
import { KpiTiles } from '../components/panel/KpiTiles'
import { PayoutToast } from '../components/panel/PayoutToast'
import { ZoneCard } from '../components/panel/ZoneCard'
import { liveNow, zoneTrend } from '../components/panel/zoneTrend'
import { AsyncView, ErrorState, Loading } from '../components/common/Status'
import { useLive, type ReplayAction } from '../state/live'
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

function ZonePanelCard({ zoneId, snapshot }: { zoneId: string; snapshot: StateSnapshot }) {
  const { api } = useLive()
  const zone = snapshot.zones.find((z) => z.zone_id === zoneId)
  const key = `${JSON.stringify(zone)}|${JSON.stringify(snapshot.kpis)}|${snapshot.triggers.length}`
  const panel = useAsync((signal) => api.zonePanel(zoneId, signal), [api, zoneId, key])
  return (
    <AsyncView {...panel} label="Loading zone…">
      {(data) => {
        const trend = zoneTrend(data, snapshot.triggers)
        return <ZoneCard key={data.zone.zone_id} panel={data} trend={trend} live={liveNow(data.zone, trend)} />
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

export default function Live() {
  const { api, snapshot, snapshotError, refresh, replayBusy } = useLive()
  const rebuilding = rebuildLabel(replayBusy)
  const navigate = useNavigate()
  const geo = useGeo(api)
  const merchant = useMerchant(snapshot?.demo_merchant_id ?? null)
  const scenarioKey = `${snapshot?.clock.scenario}|${snapshot?.clock.start}`
  /** A picked zone belongs to one scenario run; a new run falls back to the default zone. */
  const [picked, setPicked] = useState<{ run: string; zone: string } | null>(null)
  const chosen = picked?.run === scenarioKey ? picked.zone : null

  if (!snapshot) {
    return snapshotError ? <ErrorState error={snapshotError} title="Cannot reach the replay" onRetry={refresh} /> : <Loading label="Loading the city…" />
  }
  const zoneId = chosen ?? defaultZone(snapshot, merchant.data?.zone_id ?? null)

  return (
    <div className="home">
      <div className="home__map">
        <AsyncView {...geo} label="Loading wards and hexes…">
          {(data) => (
            <LiveMap
              geo={data}
              snapshot={snapshot}
              merchant={merchant.data}
              selected={zoneId}
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
      <aside className="home__panel">
        {zoneId ? <ZonePanelCard zoneId={zoneId} snapshot={snapshot} /> : null}
        <KpiTiles kpis={snapshot.kpis} />
        <ZoneExplanations snapshot={snapshot} />
        <EventFeed items={snapshot.feed} />
      </aside>
    </div>
  )
}
