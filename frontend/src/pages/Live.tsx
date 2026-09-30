/**
 * Live map page "/live" (SPEC §20, deck slide 6): the city heat map on the left; on the right the
 * triggered-zone card, KPI tiles, "Why Zone 9 got nothing" and the live event feed.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router'

import type { StateSnapshot } from '../api/types'
import { LiveMap } from '../components/map/LiveMap'
import { EventFeed } from '../components/panel/EventFeed'
import { Explanations } from '../components/panel/Explanations'
import { KpiTiles } from '../components/panel/KpiTiles'
import { ZoneCard } from '../components/panel/ZoneCard'
import { AsyncView, ErrorState, Loading } from '../components/common/Status'
import { useLive } from '../state/live'
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
  return <AsyncView {...panel} label="Loading zone…">{(data) => <ZoneCard panel={data} />}</AsyncView>
}

export default function Live() {
  const { api, snapshot, snapshotError, refresh } = useLive()
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
      </div>
      <aside className="home__panel">
        {zoneId ? <ZonePanelCard zoneId={zoneId} snapshot={snapshot} /> : null}
        <KpiTiles kpis={snapshot.kpis} />
        <Explanations explanations={snapshot.explanations} />
        <EventFeed items={snapshot.feed} />
      </aside>
    </div>
  )
}
