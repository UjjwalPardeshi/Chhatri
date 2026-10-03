/**
 * S9 Language (fs-04 section 8 and 13): a radio list of the languages the flags allow, each in its own script, a
 * preview line, and the note when some text falls back to Hindi. Static and offline-safe: the choice goes to the URL
 * and, where storage allows, to the stored preference (the provider does both).
 */
import { useLanguage } from '../hooks/useLanguage'
import { useNextBest } from '../hooks/nextBestActionBar'
import { useClaims, useCover } from '../hooks/useMiniappData'
import { isLang } from '../lib/lang'
import { useMiniapp } from '../shell/MiniappContext'
import { ScreenRoot } from '../shell/SharedStates'
import { Card, CardContent } from '../ui/card'
import { Label } from '../ui/label'
import { RadioGroup, RadioGroupItem } from '../ui/radio-group'

export function Language() {
  const { merchantId } = useMiniapp()
  const { lang, setLang, languages, t, fallbackNote } = useLanguage()
  const cover = useCover(merchantId)
  const claims = useClaims(merchantId)
  const settled = cover.state !== 'loading' && claims.state !== 'loading'
  useNextBest(settled && cover.data ? { screen: 'settings', cover: cover.data, claims: claims.data ?? [] } : null)
  return (
    <ScreenRoot name="settings" state="ready">
      <div data-testid="screen-language" className="flex flex-col gap-4">
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 px-1 text-caption font-bold text-ink-2">{t('lang.label')}</legend>
          <RadioGroup className="gap-0 overflow-hidden rounded-lg border bg-card [&>*+*]:border-t [&>*+*]:border-line-soft" value={lang} onValueChange={(next) => isLang(next) && setLang(next)} aria-label={t('lang.label')}>
            {languages.map((option) => (
              <Label key={option} htmlFor={`lang-option-${option}`} className="flex min-h-14 items-center gap-3 px-4 py-3 text-md font-medium" lang={option}>
                <RadioGroupItem id={`lang-option-${option}`} value={option} data-testid={`lang-option-${option}`} />
                {{ hi: 'हिंदी', en: 'English', mr: 'मराठी' }[option]}
              </Label>
            ))}
          </RadioGroup>
          <p className="text-caption text-muted-foreground">{t('lang.native_hint')}</p>
        </fieldset>
        <Card className="py-3">
          <CardContent className="flex flex-col gap-1 px-4">
            <p className="text-xs font-medium text-muted-foreground">{t('lang.preview')}</p>
            <p data-testid="lang-preview" className="text-md">
              {t('lang.preview')}: {t('home.btn.coverage')}
            </p>
          </CardContent>
        </Card>
        {fallbackNote ? (
          <p data-testid="lang-fallback-note" className="text-sm text-muted-foreground">
            {t('lang.fallback_note')}
          </p>
        ) : null}
      </div>
    </ScreenRoot>
  )
}
