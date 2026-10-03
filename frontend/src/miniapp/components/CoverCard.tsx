/**
 * The cover card (design system 5.2): the cover's status sentence as the backend worded it (COVER_STATUS_*), a status
 * badge, and the facts of the cover, all read from the cover view: the area, the price a day, the date it is paid up to
 * and what is used of the yearly limit. It is the navy surface of the brand with white text. Used by Home and, for a
 * merchant who already has cover, by the buy screen (`testPrefix` keeps the test ids of each screen apart).
 */
import type { ReactNode } from 'react'

import type { Cover } from '../../api/types'
import type { CopyKey, CopyParams } from '../lib/copy'
import { t } from '../lib/copy'
import { ANNUAL_WINDOW_DAYS } from '../lib/copyRules'
import { formatDate } from '../lib/format'
import type { Lang } from '../lib/lang'
import { useMiniapp } from '../shell/MiniappContext'
import { Badge } from '../ui/badge'
import { Card, CardContent } from '../ui/card'

type Tone = 'paid' | 'decided' | 'referred' | 'neutral'
type StatusBadge = { labelKey: CopyKey; params: CopyParams; tone: Tone }

const TONE: Readonly<Record<Tone, string>> = {
  paid: 'bg-paid-soft text-paid-ink',
  decided: 'bg-decided-soft text-decided',
  referred: 'bg-referred-soft text-referred-ink',
  neutral: 'bg-secondary text-secondary-foreground',
}

/** The badge of a cover status (design system 11.2), with the date a waiting cover starts in the language shown. */
export function statusBadge(cover: Cover, lang: Lang): StatusBadge | null {
  switch (cover.status) {
    case 'ACTIVE':
      return cover.premium_due
        ? { labelKey: 'cover.status.active_unpaid', params: {}, tone: 'referred' }
        : { labelKey: 'cover.status.active', params: {}, tone: 'paid' }
    case 'WAITING':
      return { labelKey: 'cover.status.waiting', params: { date: formatDate(cover.starts_on, lang) }, tone: 'decided' }
    case 'PENDING_PAYMENT':
      return { labelKey: 'cover.status.pending_payment', params: {}, tone: 'referred' }
    case 'LAPSED':
      return { labelKey: 'cover.status.lapsed', params: {}, tone: 'neutral' }
    case 'CANCELLED':
      return { labelKey: 'cover.status.cancelled', params: {}, tone: 'neutral' }
    case 'NONE':
      return null
  }
}

export type CoverRow = { key: string; label: string; value: string; testId?: string }

type CoverCardProps = {
  cover: Cover
  /** `home` or `buy`: the prefix of the card's test ids (`home-cover-card`, `home-cover-status`, ...). */
  testPrefix: string
  /** Rows after the cover's own, such as the loan instalment the merchant already pays. */
  extraRows?: readonly CoverRow[]
  children?: ReactNode
}

export function CoverCard({ cover, testPrefix, extraRows = [], children }: CoverCardProps) {
  const { lang, embedded } = useMiniapp()
  const Title = embedded ? 'h3' : 'h2'
  const badge = statusBadge(cover, lang)
  const sentence = lang === 'en' ? cover.status_text_en : cover.status_text_hi
  const hasCover = cover.status !== 'NONE'
  const rows: CoverRow[] = hasCover
    ? [
        { key: 'zone', label: t('home.row.zone', lang), value: `${cover.zone_name} (${cover.zone_id})`, testId: `${testPrefix}-zone` },
        { key: 'per_day', label: t('home.row.premium_per_day', lang), value: cover.premium_per_day_label, testId: `${testPrefix}-premium-per-day` },
        ...(cover.status === 'WAITING' && cover.starts_on
          ? [{ key: 'starts', label: t('home.row.starts_on', lang), value: formatDate(cover.starts_on, lang), testId: `${testPrefix}-starts-on` }]
          : []),
        ...(cover.prepaid_through
          ? [{ key: 'paid', label: t('home.row.paid_through', lang), value: formatDate(cover.prepaid_through, lang), testId: `${testPrefix}-prepaid-through` }]
          : []),
        ...extraRows,
      ]
    : []
  const used =
    cover.amount_claimed_label !== null && cover.annual_limit_label !== null
      ? t('home.used', lang, { window_days: ANNUAL_WINDOW_DAYS, used: cover.amount_claimed_label, limit: cover.annual_limit_label })
      : null
  return (
    <Card data-testid={`${testPrefix}-cover-card`} data-status={cover.status} className="gap-3 border-0 bg-navy py-4 text-on-navy">
      <CardContent className="flex flex-col gap-3 px-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Title className="text-caption font-medium text-on-navy-2">{t('home.title', lang)}</Title>
          {badge ? (
            <Badge variant="secondary" data-testid={`${testPrefix}-cover-badge`} className={TONE[badge.tone]}>
              {t(badge.labelKey, lang, badge.params)}
            </Badge>
          ) : null}
        </div>
        <p data-testid={`${testPrefix}-cover-status`} className="text-lg font-bold leading-snug text-on-navy">
          {sentence}
        </p>
        {rows.length > 0 ? (
          <dl className="flex flex-col gap-2 border-t border-navy-line pt-3">
            {rows.map((row) => (
              <div key={row.key} className="flex items-baseline justify-between gap-4">
                <dt className="text-caption text-on-navy-2">{row.label}</dt>
                <dd data-testid={row.testId} className="num text-right text-md font-bold text-on-navy">
                  {row.value}
                </dd>
              </div>
            ))}
          </dl>
        ) : null}
        {used ? (
          <p data-testid={`${testPrefix}-annual-used`} className="border-t border-navy-line pt-3 text-caption text-on-navy-2">
            {used}
          </p>
        ) : null}
        {children}
      </CardContent>
    </Card>
  )
}
