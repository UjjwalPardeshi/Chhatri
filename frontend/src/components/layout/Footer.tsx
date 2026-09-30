/**
 * Attributions (SPEC §5.1, §20) and the always-simulated components (SPEC §0.1). CARTO and
 * OpenStreetMap are credited only while their tiles are on screen; the wards (DataMeet) always are.
 */
import { useBasemap } from '../../state/tileStatus'
import { useLive } from '../../state/live'

export function Footer() {
  const { mock } = useLive()
  const tiles = useBasemap() === 'tiles'
  return (
    <footer className="app-footer">
      {tiles ? (
        <span>
          Map tiles © <a href="https://carto.com/attributions">CARTO</a> · © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors
        </span>
      ) : null}
      <span>
        Wards: <a href="https://github.com/datameet/Municipal_Spatial_Data">DataMeet</a> (CC BY-SA 2.5 India)
      </span>
      <span>
        Rainfall: <a href="https://open-meteo.com/">Open-Meteo</a>
      </span>
      <span className="app-footer__sim">Sales, alerts, KYC, payouts, lender and Soundbox are simulated</span>
      {mock ? <span className="badge badge--amber">Mock data</span> : null}
    </footer>
  )
}
