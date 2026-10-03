/**
 * The app bar (fs-04 section 8, shell ids): the screen's title as the page's `h1` (an `h2` inside the console's frame), a Back button on a screen below a
 * tab, the replay clock as simulated time, one SIMULATED summary badge and the language button (the globe opens S9). On the
 * standalone route, where no console control bar moves the replay, the clock opens the demo clock sheet.
 */
import { ArrowLeft, Globe } from 'lucide-react'

import { SCREEN_DEFS } from '../screens/registry'
import { t } from '../lib/copy'
import { formatDateTime } from '../lib/format'
import { Button } from '../ui/button'
import { DemoClockSheet } from './DemoClockSheet'
import { useMiniapp } from './MiniappContext'
import { ModeBadge } from './SharedStates'

export function AppBar() {
  const { lang, url, now, embedded } = useMiniapp()
  const Title = embedded ? 'h2' : 'h1'
  const { titleKey, parent } = SCREEN_DEFS[url.screen]
  return (
    <header data-testid="app-appbar" className="flex min-h-14 shrink-0 items-center gap-1 border-b bg-card pr-1 pl-2">
      {parent ? (
        <Button variant="ghost" size="icon" data-testid="app-back" aria-label={t('app.back', lang)} onClick={() => url.go({ screen: parent })}>
          <ArrowLeft aria-hidden="true" />
        </Button>
      ) : null}
      <div className="min-w-0 flex-1 px-2 py-1">
        <Title className="line-clamp-2 break-words text-lg font-bold leading-tight">{t(titleKey, lang)}</Title>
        {embedded ? (
          <time data-testid="app-clock" dateTime={now ?? undefined} className="mt-0.5 block text-2xs leading-tight text-muted-foreground">
            {t('app.clock', lang, { time: formatDateTime(now, lang) })}
          </time>
        ) : (
          <DemoClockSheet />
        )}
      </div>
      <ModeBadge mode="SIMULATED" />
      <Button
        variant="ghost"
        size="icon"
        data-testid="app-lang-button"
        aria-label={t('lang.label', lang)}
        onClick={() => {
          if (url.screen !== 'settings') url.go({ screen: 'settings' })
        }}
      >
        <Globe aria-hidden="true" />
      </Button>
    </header>
  )
}
