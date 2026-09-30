/** Top bar (SPEC §20): wordmark, page navigation, integration badges, sound, connection state. */
import { useEffect, useRef } from 'react'
import { Link, NavLink, useLocation } from 'react-router'

import type { ScenarioName, StateSnapshot } from '../../api/types'
import { DEMO_MERCHANT } from '../../content/deck'
import { useLive } from '../../state/live'
import { Brand } from './Brand'
import { ConnectionPill } from './ConnectionPill'
import { SCENARIO_OPTIONS } from './ControlBar'
import { IntegrationBadges } from './IntegrationBadges'
import { SoundToggle } from './SoundToggle'

/** Room left of the active link when it is scrolled into view on a phone. */
const NAV_SCROLL_MARGIN = 24

/** Keeps the active link visible in the sideways-scrolling phone nav (never scrolls the page). */
function useActiveLinkInView(pathname: string) {
  const navRef = useRef<HTMLElement>(null)
  useEffect(() => {
    const nav = navRef.current
    const active = nav?.querySelector<HTMLElement>('.is-active')
    if (!nav || !active || nav.scrollWidth <= nav.clientWidth) return
    const left = active.offsetLeft - NAV_SCROLL_MARGIN
    const right = active.offsetLeft + active.offsetWidth + NAV_SCROLL_MARGIN
    if (left < nav.scrollLeft || right > nav.scrollLeft + nav.clientWidth) nav.scrollTo({ left: Math.max(0, left), behavior: 'smooth' })
  }, [pathname])
  return navRef
}

/**
 * The "Merchant phone" link's merchant (binding decision B5). A scenario being loaded decides
 * first, so a click during the switch already opens the new merchant; then the clock's scenario
 * (updated as soon as the load returns, before `demo_merchant_id` arrives with the next
 * snapshot); the snapshot's id is the fallback when no scenario is loaded.
 */
export function phoneMerchant(snapshot: Pick<StateSnapshot, 'clock' | 'demo_merchant_id'> | null, loading: ScenarioName | null = null): string {
  const scenario = loading ?? snapshot?.clock.scenario
  if (scenario) return SCENARIO_OPTIONS[scenario].merchant
  return snapshot?.demo_merchant_id ?? DEMO_MERCHANT
}

export function Header({ openCases }: { openCases: number }) {
  const { snapshot, loadingScenario } = useLive()
  const { pathname } = useLocation()
  const navRef = useActiveLinkInView(pathname)
  const phoneId = phoneMerchant(snapshot, loadingScenario)
  const links = [
    { to: '/', label: 'Overview', end: true },
    { to: '/live', label: 'Live map' },
    { to: '/claims', label: 'Claims', badge: openCases },
    { to: `/merchant/${phoneId}`, label: 'Merchant phone' },
    { to: '/audit', label: 'Audit' },
    { to: '/backtest', label: 'Backtest' },
    { to: '/policy', label: 'Policy' },
  ]
  return (
    <header className="app-header">
      <Link to="/" className="brand" aria-label="Chhatri overview">
        <Brand />
      </Link>
      <nav className="app-nav" aria-label="Pages" ref={navRef}>
        {links.map((link) => (
          <NavLink key={link.label} to={link.to} end={link.end} className={({ isActive }) => `app-nav__link ${isActive ? 'is-active' : ''}`}>
            {link.label}
            {link.badge ? (
              <span className="app-nav__count" aria-label={`${link.badge} open`}>
                {link.badge}
              </span>
            ) : null}
          </NavLink>
        ))}
      </nav>
      <div className="app-header__right">
        <ConnectionPill />
        <IntegrationBadges />
        <SoundToggle />
      </div>
    </header>
  )
}
