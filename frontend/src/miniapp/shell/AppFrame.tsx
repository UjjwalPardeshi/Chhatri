/**
 * The mini-app frame on the merchant page (fs-04 4.1): the console's `.phone` bezel on an outer element outside
 * `.miniapp` (the one console class the mini-app code uses), a strip with the "Open full screen" link, and the app
 * inside. The bezel is the containing block for overlays. The link keeps `mock`, `presenter` and `lang`, and opens the
 * same screen full size. Loaded lazily by the merchant page, and only while `n1_miniapp` is on.
 */
import { ExternalLink } from 'lucide-react'
import { Link, useLocation } from 'react-router'

import { miniappHref } from '../hooks/useMiniappUrl'
import { t } from '../lib/copy'
import { MiniappProvider, useMiniapp } from './MiniappContext'
import { MiniappView } from './MiniappView'

function Frame() {
  const { search } = useLocation()
  const { lang, merchantId, url } = useMiniapp()
  const target = { screen: url.screen, ...(url.claim ? { claim: url.claim } : {}), ...(url.decision ? { decision: url.decision } : {}) }
  return (
    <section className="phone phone--app" data-testid="app-frame" aria-label={t('app.frame_label', lang)}>
      <div className="flex shrink-0 justify-end bg-card px-3">
        <Link
          to={miniappHref(`/merchant/${merchantId}/app`, search, target)}
          data-testid="app-open-fullscreen"
          lang={lang}
          className="inline-flex min-h-11 items-center gap-1 text-xs font-medium text-link"
        >
          {t('app.fullscreen', lang)}
          <ExternalLink className="size-3.5" aria-hidden="true" />
        </Link>
      </div>
      <div className="min-h-0 flex-1">
        <MiniappView />
      </div>
    </section>
  )
}

export default function AppFrame({ merchantId }: { merchantId: string }) {
  return (
    <MiniappProvider merchantId={merchantId} embedded>
      <Frame />
    </MiniappProvider>
  )
}
