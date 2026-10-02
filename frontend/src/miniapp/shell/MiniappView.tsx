/**
 * The mini-app itself, drawn inside a `MiniappProvider`: the `.miniapp` root (with the active language and `app-root`)
 * holding the app bar, the screen, the next-best bar and the tab bar. The console frame and the standalone route both
 * render this, so they show the same app from the same live state. A scenario load resets the app to Home (fs-04 6.3).
 */
import { useLiveEvent } from '../../state/live'
import { MiniappRoot } from '../MiniappRoot'
import { AppBar } from './AppBar'
import { useMiniapp } from './MiniappContext'
import { NextBestBar } from './NextBestBar'
import { ScreenHost } from './ScreenHost'
import { StaticBanner } from './StaticBanner'
import { TabBar } from './TabBar'
import { ToastHost } from './ToastHost'

function Shell() {
  const { url } = useMiniapp()
  useLiveEvent(['scenario'], () => url.go({ screen: 'home' }, { replace: true }))
  return (
    <div className="flex h-full min-h-0 flex-col bg-background text-foreground">
      <StaticBanner />
      <AppBar />
      <ScreenHost />
      <NextBestBar />
      <TabBar />
      <ToastHost />
    </div>
  )
}

export function MiniappView() {
  const { lang } = useMiniapp()
  return (
    <MiniappRoot lang={lang}>
      <Shell />
    </MiniappRoot>
  )
}
