/**
 * The consent block of S3 (N6, fs-07 section 9.5, copy deck 14.1), shown above `buy-check` while `n6_consents` is on
 * and the merchant has no cover: the notice and its version, then three boxes that start unticked. Sales and
 * settlement are "Needed for cover", the slip is "Optional". The purposes, their order and the notice version come
 * from `GET /consents`; the words are the deck's. The screen owns the ticks, because the quote call sends them.
 */
import type { Consent, ConsentPurpose } from '../api/rights'
import { t, type CopyKey } from '../lib/copy'
import type { Lang } from '../lib/lang'
import { Badge } from '../ui/badge'

/** The two boxes needed for cover first, then the optional one (fs-07 9.5); the API's order otherwise. */
const requiredFirst = (consents: readonly Consent[]): Consent[] => consents.toSorted((a, b) => Number(b.required_to_buy) - Number(a.required_to_buy))

export const consentBoxId = (purpose: ConsentPurpose): string => `buy-consent-${purpose}`

/** The first required purpose still unticked (its box test id), or null once every required box is ticked. */
export function firstUntickedBox(consents: readonly Consent[], ticked: ReadonlySet<ConsentPurpose>): string | null {
  const open = requiredFirst(consents).find((consent) => consent.required_to_buy && !ticked.has(consent.purpose))
  return open ? consentBoxId(open.purpose) : null
}

type Props = {
  consents: readonly Consent[]
  ticked: ReadonlySet<ConsentPurpose>
  lang: Lang
  disabled: boolean
  onToggle: (purpose: ConsentPurpose, on: boolean) => void
}

export function BuyConsent({ consents, ticked, lang, disabled, onToggle }: Props) {
  const version = consents[0]?.current_notice_version ?? ''
  const incomplete = firstUntickedBox(consents, ticked) !== null
  return (
    <section aria-labelledby="buy-consent-notice" className="flex flex-col gap-3 rounded-lg border bg-card p-4">
      <p id="buy-consent-notice" data-testid="buy-consent-notice" className="text-sm">
        {t('buy.consent.text', lang)}
      </p>
      <p data-testid="buy-consent-version" className="text-caption text-muted-foreground">
        {t('buy.consent.version', lang, { version })}
      </p>
      <ul className="flex flex-col gap-2">
        {requiredFirst(consents).map((consent) => {
          const id = consentBoxId(consent.purpose)
          return (
            <li key={consent.purpose} className="flex min-h-11 items-start gap-3 py-1">
              <input
                id={id}
                data-testid={id}
                type="checkbox"
                className="mt-1 size-5 shrink-0 accent-primary"
                checked={ticked.has(consent.purpose)}
                disabled={disabled}
                onChange={(event) => onToggle(consent.purpose, event.target.checked)}
              />
              <label htmlFor={id} className="flex flex-col gap-1 text-sm">
                {t(`buy.consent.box.${consent.purpose}` as CopyKey, lang)}
                <Badge variant="outline" className="w-fit">
                  {t(consent.required_to_buy ? 'buy.consent.tag.required' : 'buy.consent.tag.optional', lang)}
                </Badge>
              </label>
            </li>
          )
        })}
      </ul>
      {incomplete ? (
        <p data-testid="buy-consent-hint" className="text-sm text-secondary-foreground">
          {t('buy.consent.hint', lang)}
        </p>
      ) : null}
    </section>
  )
}
