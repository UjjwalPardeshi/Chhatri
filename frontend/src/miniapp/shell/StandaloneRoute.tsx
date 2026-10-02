/**
 * `/merchant/:id/app` (fs-04 4.2): the mini-app full viewport, centred and at most 430 px wide on a desktop, with no
 * console chrome. It sits inside `LiveProvider` and outside `AppShell` (App.tsx), so it reads the same live state.
 * While `n1_miniapp` is off, App.tsx redirects before this chunk is requested. A bad merchant id shows "Unknown merchant".
 */
import { useParams } from 'react-router'

import { DEFAULT_LANG } from '../lib/lang'
import { t } from '../lib/copy'
import { merchantIdFromPath } from '../hooks/useMiniappUrl'
import { MiniappProvider } from './MiniappContext'
import { MiniappView } from './MiniappView'

export default function StandaloneRoute() {
  const merchantId = merchantIdFromPath(useParams().id)
  if (merchantId === null) {
    return (
      <div data-testid="app-unknown-merchant" role="alert" lang={DEFAULT_LANG} className="flex h-dvh items-center justify-center p-6 text-md font-medium">
        {t('app.unknown_merchant', DEFAULT_LANG)}
      </div>
    )
  }
  return (
    <MiniappProvider key={merchantId} merchantId={merchantId}>
      <div data-testid="app-standalone" className="flex h-dvh w-full justify-center bg-secondary">
        <div className="h-full w-full max-w-[430px] bg-background">
          <MiniappView />
        </div>
      </div>
    </MiniappProvider>
  )
}
