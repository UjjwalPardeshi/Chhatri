/**
 * Attributions (SPEC §5.1, §20) and the always-simulated components (SPEC §0.1). OpenStreetMap is
 * always credited (tiles, and the geometry of the MMR context cells); the wards (DataMeet) too.
 */
import { useLive } from '../../state/live'

export function Footer() {
  const { mock } = useLive()
  return (
    <footer className="app-footer">
      <span>
        Map: © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors (ODbL)
      </span>
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
