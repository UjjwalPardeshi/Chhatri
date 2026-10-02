/** The parts of the buy screen that follow the check: the quote (BLOCKED or OK), the payment link and its label, and the paid card. */
import type { CoverQuote, PremiumPayment } from '../../api/types'
import { ModeBadge } from '../components/ModeBadge'
import { t } from '../lib/copy'
import { formatDate } from '../lib/format'
import type { Lang } from '../lib/lang'
import { Button } from '../ui/button'
import { Card, CardContent } from '../ui/card'
import { NetworkButton } from '../shell/SharedStates'

export type LinkMode = 'SIMULATED' | 'LIVE'

/** The link is simulated when its source says so; anything else is a real Paytm link. */
export const linkMode = (premium: PremiumPayment): LinkMode => (premium.source === 'simulated' ? 'SIMULATED' : 'LIVE')

function Row({ label, value, testId }: { label: string; value: string; testId: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className="text-sm text-secondary-foreground">{label}</dt>
      <dd data-testid={testId} className="num shrink-0 text-right text-md font-medium">
        {value}
      </dd>
    </div>
  )
}

export function QuoteCard({ quote, lang, firstDays }: { quote: CoverQuote; lang: Lang; firstDays: number }) {
  const date = formatDate(quote.starts_on, lang)
  const blocked = quote.outcome === 'BLOCKED'
  return (
    <Card data-testid="buy-result" data-outcome={quote.outcome} className="gap-3 py-4">
      <CardContent className="flex flex-col gap-3 px-4">
        <p className="text-lg font-medium">{t(blocked ? 'buy.outcome.blocked' : 'buy.outcome.ok', lang, { date })}</p>
        <p className="text-sm text-muted-foreground">{lang === 'hi' ? quote.reason_hi : quote.reason_en}</p>
        <dl className="flex flex-col gap-2">
          <Row label={t('buy.row.starts', lang)} value={date} testId="buy-starts-on" />
          <Row label={t('buy.row.per_day', lang)} value={quote.premium_per_day_label} testId="buy-price-per-day" />
          <Row label={t('buy.row.first_payment', lang, { first_days: firstDays })} value={quote.first_payment_label} testId="buy-first-payment" />
        </dl>
        {blocked ? <p className="text-sm">{t('buy.blocked_note', lang)}</p> : null}
        <p className="text-caption text-muted-foreground">{t('buy.consent.notice', lang)}</p>
      </CardContent>
    </Card>
  )
}

type LinkProps = { premium: PremiumPayment; lang: Lang; busy: boolean; onSimulate: () => void }

export function LinkCard({ premium, lang, busy, onSimulate }: LinkProps) {
  const mode = linkMode(premium)
  return (
    <Card className="gap-3 py-4">
      <CardContent className="flex flex-col gap-3 px-4">
        <div className="flex flex-wrap items-center gap-2">
          <ModeBadge mode={mode} testId="buy-link-mode" />
          {mode === 'SIMULATED' ? <span className="text-sm">{t('buy.link.simulated', lang)}</span> : null}
        </div>
        <p className="text-caption text-muted-foreground">
          {t('buy.link_label', lang)}: <span className="mono break-all">{premium.link_url}</span>
        </p>
        {mode === 'SIMULATED' ? (
          <NetworkButton data-testid="buy-simulate-pay" size="lg" disabled={busy} onClick={onSimulate}>
            {t('buy.simulate', lang)}
          </NetworkButton>
        ) : (
          <Button data-testid="buy-pay-live" size="lg" disabled={busy} onClick={() => window.open(premium.link_url ?? '', '_blank', 'noopener,noreferrer')}>
            {t('buy.pay', lang)}
          </Button>
        )}
        <p className="text-sm text-muted-foreground">{t('buy.pending', lang)}</p>
      </CardContent>
    </Card>
  )
}

export function PaidCard({ premium, lang }: { premium: PremiumPayment; lang: Lang }) {
  return (
    <Card data-testid="buy-paid" className="gap-2 border-paid bg-paid-soft py-4">
      <CardContent className="flex flex-col gap-1 px-4">
        <p className="text-lg font-medium text-paid-ink">{t('buy.paid', lang)}</p>
        <p className="text-sm">
          {t('buy.row.starts', lang)}: <span className="num font-medium">{formatDate(premium.covers_from, lang)}</span>
        </p>
      </CardContent>
    </Card>
  )
}
