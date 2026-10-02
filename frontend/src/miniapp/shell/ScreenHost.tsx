/**
 * The scrolling area between the app bar and the next-best bar: it draws the screen the URL names (an unknown one is
 * Home). It is the page's `main` landmark on its own, and a plain region inside the console, which has its own.
 */
import { SCREEN_DEFS } from '../screens/registry'
import { useMiniapp } from './MiniappContext'

export function ScreenHost() {
  const { url, embedded } = useMiniapp()
  const { Component } = SCREEN_DEFS[url.screen]
  const Host = embedded ? 'div' : 'main'
  return (
    <Host className="min-h-0 flex-1 overflow-y-auto">
      <Component key={url.screen} />
    </Host>
  )
}
