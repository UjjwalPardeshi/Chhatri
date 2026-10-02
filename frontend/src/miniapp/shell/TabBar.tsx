/**
 * The tab bar (fs-04 4.4): a `nav` of three links, Home, Claims and Help, with `aria-current="page"` and 44 px targets
 * or more. The open tab links to the URL it is already at, which the router treats as a replace, so it adds no history entry.
 */
import { ClipboardList, House, LifeBuoy } from 'lucide-react'
import { Link } from 'react-router'

import { TABS, SCREEN_DEFS, type Tab } from '../screens/registry'
import { t } from '../lib/copy'
import { cn } from '../lib/cn'
import { useMiniapp } from './MiniappContext'

const ICONS = { home: House, claims: ClipboardList, help: LifeBuoy } as const satisfies Record<Tab, unknown>

export function TabBar() {
  const { lang, url } = useMiniapp()
  const active = SCREEN_DEFS[url.screen].tab
  return (
    <nav aria-label={t('app.tabs', lang)} data-testid="app-tabbar" className="grid shrink-0 grid-cols-3 border-t bg-card">
      {TABS.map(({ tab, screen, labelKey }) => {
        const Icon = ICONS[tab]
        const current = active === tab
        return (
          <Link
            key={tab}
            to={url.href({ screen })}
            data-testid={`app-tab-${tab}`}
            aria-current={current ? 'page' : undefined}
            className={cn('flex min-h-14 flex-col items-center justify-center gap-0.5 text-xs font-medium', current ? 'text-primary' : 'text-ink-3')}
          >
            <Icon className="size-5" aria-hidden="true" />
            <span>{t(labelKey, lang)}</span>
          </Link>
        )
      })}
    </nav>
  )
}
