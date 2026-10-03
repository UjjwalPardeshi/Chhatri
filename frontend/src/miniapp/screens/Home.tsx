/**
 * S1 Home (fs-04 section 8): am I covered, what is happening, what next, at a glance. The greeting, the alert banner
 * while an alert is in force in the zone, the cover card, the expected day, the latest claim and the shortcuts, then
 * one next step from the global list of the rules (H21). Everything is an API field: the cover sentence is the
 * catalogue's, the amounts are the API's labels. Home creates no payment link and shows no offer of any kind (X8).
 */
import { CloudRain } from 'lucide-react'
import { Link } from 'react-router'

import type { ClaimItem, Cover } from '../../api/types'
import { isFeatureEnabled } from '../../features'
import { AlertBanner } from '../components/AlertBanner'
import { CoverCard, type CoverRow } from '../components/CoverCard'
import { ListGroup, ListRowLink } from '../components/ListRow'
import { ModeBadge } from '../components/ModeBadge'
import { useNextBest } from '../hooks/nextBestActionBar'
import { useClaims, useCover } from '../hooks/useMiniappData'
import type { Resource } from '../hooks/useResource'
import { t } from '../lib/copy'
import { formatClock, formatDate, formatDateTime } from '../lib/format'
import type { Lang } from '../lib/lang'
import { useLive } from '../../state/live'
import { useMiniapp } from '../shell/MiniappContext'
import { ErrorState, ResourceScreen, ScreenRoot } from '../shell/SharedStates'
import { Button } from '../ui/button'
import { Card } from '../ui/card'
import { Skeleton } from '../ui/skeleton'
import { HomeClaimCard } from './HomeClaimCard'

function HomeSkeleton() {
  const { lang } = useMiniapp()
  return (
    <output data-testid="app-skeleton" aria-label={t('state.loading', lang)} className="flex flex-col gap-3">
      <Skeleton className="h-7 w-1/2" />
      <Skeleton className="h-44 w-full rounded-lg" />
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-16 w-full" />
    </output>
  )
}

const firstName = (full: string): string => full.trim().split(/\s+/)[0] ?? full

function Greeting() {
  const { lang, merchant } = useMiniapp()
  if (merchant.data === null) return <Skeleton className="h-7 w-1/2" />
  const name = firstName(lang === 'en' ? merchant.data.owner_name : merchant.data.owner_name_hi)
  return (
    <p data-testid="home-greeting" className="text-xl font-bold leading-tight">
      {t('home.greeting', lang, { name })}
    </p>
  )
}

/** "19 August, 14:00 to 20:00": the end shows its date only when it is not the day the alert starts. */
function alertWindow(from: string, to: string, lang: Lang): { valid_from: string; valid_to: string } {
  const sameDay = formatDate(from, lang) === formatDate(to, lang)
  return { valid_from: formatDateTime(from, lang), valid_to: sameDay ? formatClock(to) : formatDateTime(to, lang) }
}

function HomeAlert({ cover }: { cover: Cover }) {
  const { lang } = useMiniapp()
  const { snapshot } = useLive()
  const zone = snapshot?.zones.find((z) => z.zone_id === cover.zone_id)?.alert ?? null
  const known = zone !== null && zone.id === cover.alert_id ? zone : null
  const alertId = cover.alert_id ?? ''
  const title = known ? t('home.alert.banner', lang, { alert_id: known.id, ...alertWindow(known.valid_from, known.valid_to, lang) }) : t('alert.id', lang, { alert_id: alertId })
  const body = cover.status === 'ACTIVE' ? t('home.alert.covered', lang) : t('home.alert.not_covered', lang)
  return (
    <AlertBanner tone="warning" icon={CloudRain} testId="home-alert-banner" title={title} badge={<ModeBadge mode="SIMULATED" testId="home-alert-mode" />}>
      <p>{body}</p>
    </AlertBanner>
  )
}

function ClaimSlot({ claims }: { claims: Resource<ClaimItem[]> }) {
  const latest = claims.data?.[0] ?? null
  if (latest) return <HomeClaimCard item={latest} />
  if (claims.error && claims.data === null) {
    return (
      <div data-testid="home-claim-error">
        <ErrorState error={claims.error} onRetry={claims.reload} />
      </div>
    )
  }
  if (claims.state === 'loading') return <Skeleton data-testid="home-claim-loading" className="h-24 w-full" />
  return null
}

function ExpectedDay({ label }: { label: string }) {
  const { lang, embedded } = useMiniapp()
  const Title = embedded ? 'h3' : 'h2'
  return (
    <Card data-testid="home-expected-day" className="min-h-14 flex-row items-center justify-between gap-3 px-4 py-3">
      <Title className="text-md font-bold">{t('home.expected', lang)}</Title>
      <span className="num text-xl font-bold">{label}</span>
    </Card>
  )
}

function HomeBody({ cover, claims }: { cover: Cover; claims: Resource<ClaimItem[]> }) {
  const { lang, merchant, url } = useMiniapp()
  const loan = merchant.data?.loan ?? null
  const extraRows: CoverRow[] = loan ? [{ key: 'instalment', label: t('home.row.instalment', lang), value: loan.daily_instalment_label, testId: 'home-instalment' }] : []
  const expected = merchant.data?.expected_today_label ?? null
  return (
    <>
      <Greeting />
      {cover.alert_active ? <HomeAlert cover={cover} /> : null}
      <CoverCard cover={cover} testPrefix="home" extraRows={extraRows} />
      {expected ? <ExpectedDay label={expected} /> : null}
      <ClaimSlot claims={claims} />
      {cover.status === 'NONE' ? (
        <Button asChild size="lg">
          <Link to={url.href({ screen: 'buy' })} data-testid="home-open-buy">
            {t('home.btn.buy', lang)}
          </Link>
        </Button>
      ) : null}
      <ListGroup>
        <ListRowLink to={url.href({ screen: 'coverage' })} data-testid="home-open-coverage" title={t('home.btn.coverage', lang)} />
        {isFeatureEnabled('n2_ask_chhatri') ? <ListRowLink to={url.href({ screen: 'ask' })} data-testid="home-open-ask" title={t('home.btn.ask', lang)} /> : null}
      </ListGroup>
    </>
  )
}

export function Home() {
  const { merchantId, merchant } = useMiniapp()
  const cover = useCover(merchantId)
  const claims = useClaims(merchantId)
  const shown = (cover.state === 'ready' || cover.state === 'offline') && cover.data !== null
  const settled = claims.state !== 'loading' && (merchant.data !== null || merchant.error !== null)
  useNextBest(shown && settled && cover.data ? { screen: 'home', cover: cover.data, claims: claims.data ?? [] } : null)

  if (cover.state !== 'error' && merchant.error && merchant.data === null) {
    return (
      <ScreenRoot name="home" state="error">
        <ErrorState error={merchant.error} onRetry={merchant.reload} />
      </ScreenRoot>
    )
  }
  return (
    <ResourceScreen name="home" resource={cover} skeleton={<HomeSkeleton />}>
      {(data) => <HomeBody cover={data} claims={claims} />}
    </ResourceScreen>
  )
}
