/**
 * The static demo banner (screens-and-flows 8, N7, copy deck `offline.static`): on the standalone route running on the
 * in-browser mock, one line says the data is made up and nothing is sent anywhere. "Got it" folds it away for the tab;
 * the SIMULATED badge of the app bar stays, so the honesty never goes. The console frame never shows it.
 */
import { useState } from 'react'

import { useLive } from '../../state/live'
import { t } from '../lib/copy'
import { Button } from '../ui/button'
import { useMiniapp } from './MiniappContext'

export const STATIC_BANNER_KEY = 'chhatri.static-banner'

function readDismissed(): boolean {
  try {
    return window.sessionStorage.getItem(STATIC_BANNER_KEY) === '1'
  } catch {
    return false
  }
}

function writeDismissed(): void {
  try {
    window.sessionStorage.setItem(STATIC_BANNER_KEY, '1')
  } catch {
    // Storage blocked (a private window): the banner folds for this page only.
  }
}

export function StaticBanner() {
  const { lang, embedded } = useMiniapp()
  const { mock } = useLive()
  const [dismissed, setDismissed] = useState(readDismissed)
  if (embedded || !mock || dismissed) return null
  return (
    <div data-testid="app-static-banner" role="note" className="flex shrink-0 items-center gap-3 border-b bg-demo-soft px-4 py-2 text-xs print:hidden">
      <p className="min-w-0 flex-1">{t('offline.static', lang)}</p>
      <Button
        variant="outline"
        data-testid="app-static-banner-close"
        onClick={() => {
          writeDismissed()
          setDismissed(true)
        }}
      >
        {t('explain.btn.got_it', lang)}
      </Button>
    </div>
  )
}
