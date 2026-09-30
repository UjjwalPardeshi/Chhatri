/** Top bar (SPEC §20): wordmark, page navigation, integration badges, sound, connection state. */
import { useEffect, useRef } from 'react'
import { Link, NavLink, useLocation } from 'react-router'

import { useLive } from '../../state/live'
import { Brand } from './Brand'
import { ConnectionPill } from './ConnectionPill'
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

export function Header({ openCases }: { openCases: number }) {
  const { snapshot } = useLive()
  const { pathname } = useLocation()
  const navRef = useActiveLinkInView(pathname)
  const phoneId = snapshot?.demo_merchant_id ?? 'S-0142'
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
