/**
 * S8 Help (fs-04 section 8): one place for everything that is not a claim. Rows for what the cover is for, the
 * language and the prototype note (the rows of other waves appear with their flags and are not drawn until then), the
 * insurance words as buttons for the jargon lens, and the way to raise a wrong amount. Static: it never calls the API
 * except for the next step of the bar.
 */
import { ChevronRight } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { isFeatureEnabled } from '../../features'
import { JargonTerms } from '../components/JargonTerms'
import { ModeBadge } from '../components/ModeBadge'
import { TERM_IDS } from '../glossary'
import { useNextBest } from '../hooks/nextBestActionBar'
import { useClaims, useCover } from '../hooks/useMiniappData'
import type { CopyKey } from '../lib/copy'
import { t } from '../lib/copy'
import { useMiniapp } from '../shell/MiniappContext'
import { ScreenRoot } from '../shell/SharedStates'
import { Card, CardContent } from '../ui/card'

const MODES = [
  { mode: 'SIMULATED', hint: 'origin.SIMULATED.hint' },
  { mode: 'FALLBACK', hint: 'mode.FALLBACK.hint' },
  { mode: 'LIVE', hint: 'origin.LIVE.hint' },
] as const satisfies readonly { mode: 'SIMULATED' | 'FALLBACK' | 'LIVE'; hint: CopyKey }[]

function RowLink({ to, testId, label }: { to: string; testId: string; label: string }) {
  return (
    <Link to={to} data-testid={testId} className="flex min-h-12 items-center justify-between gap-3 rounded-lg border bg-card px-4 py-3 text-md font-medium outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50">
      <span>{label}</span>
      <ChevronRight className="size-5 shrink-0 text-muted-foreground" aria-hidden="true" />
    </Link>
  )
}

function Heading({ children }: { children: ReactNode }) {
  const { embedded } = useMiniapp()
  const Title = embedded ? 'h3' : 'h2'
  return <Title className="text-md font-medium">{children}</Title>
}

export function Help() {
  const { lang, merchantId, url } = useMiniapp()
  const cover = useCover(merchantId)
  const claims = useClaims(merchantId)
  const settled = cover.state !== 'loading' && claims.state !== 'loading'
  useNextBest(settled && cover.data ? { screen: 'help', cover: cover.data, claims: claims.data ?? [] } : null)
  return (
    <ScreenRoot name="help" state="ready">
      <nav aria-label={t('nav.help', lang)} className="flex flex-col gap-3">
        <RowLink to={url.href({ screen: 'coverage' })} testId="help-coverage" label={t('explain.title', lang)} />
        {isFeatureEnabled('n2_ask_chhatri') ? <RowLink to={url.href({ screen: 'ask' })} testId="help-ask" label={t('ask.title', lang)} /> : null}
        {isFeatureEnabled('n5_grievances') ? <RowLink to={url.href({ screen: 'grievances' })} testId="help-grievances" label={t('grv.title', lang)} /> : null}
        {isFeatureEnabled('n6_consents') ? <RowLink to={url.href({ screen: 'consents' })} testId="help-consents" label={t('consent.title', lang)} /> : null}
        <RowLink to={url.href({ screen: 'settings' })} testId="help-language" label={t('lang.label', lang)} />
        {isFeatureEnabled('n3_slip_precheck') ? <RowLink to={url.href({ screen: 'slip' })} testId="help-slip" label={t('slip.help_row', lang)} /> : null}
      </nav>
      <Card data-testid="help-dispute" className="py-3">
        <CardContent className="px-4 text-sm">{t('help.dispute.hint', lang)}</CardContent>
      </Card>
      <section className="flex flex-col gap-1">
        <Heading>{t('help.glossary.title', lang)}</Heading>
        <JargonTerms ids={TERM_IDS} testId="help-glossary" />
      </section>
      <Card data-testid="help-about" className="py-4">
        <CardContent className="flex flex-col gap-3 px-4">
          <Heading>{t('help.about.title', lang)}</Heading>
          <p className="text-sm">{t('help.about.text', lang)}</p>
          <ul className="flex flex-col gap-2">
            {MODES.map(({ mode, hint }) => (
              <li key={mode} className="flex items-start gap-2 text-sm">
                <ModeBadge mode={mode} testId={`help-mode-${mode}`} />
                <span>{t(hint, lang)}</span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </ScreenRoot>
  )
}
