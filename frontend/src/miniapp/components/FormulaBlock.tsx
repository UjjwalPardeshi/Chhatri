/**
 * The formula of a decision (fs-04 10.1): the engine's own words, the app's language large and the other small, each
 * in its own `lang` element and each one text node (`½ × ₹4,380 × 63% = ₹1,380`), never `aria-hidden`. Nothing is
 * computed here. Marathi has no formula from the engine, so it shows the Hindi one large.
 */
import { cn } from '../lib/cn'
import type { Lang } from '../lib/lang'
import { useMiniapp } from '../shell/MiniappContext'

type FormulaProps = { en: string; hi: string; testId: string; className?: string }

export function FormulaBlock({ en, hi, testId, className }: FormulaProps) {
  const { lang } = useMiniapp()
  const first: Lang = lang === 'en' ? 'en' : 'hi'
  const second: Lang = first === 'en' ? 'hi' : 'en'
  const text = { en, hi }
  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <p data-testid={testId} lang={first === lang ? undefined : first} className="num text-xl font-medium leading-snug text-foreground">
        {text[first]}
      </p>
      <p data-testid={`${testId}-other`} lang={second} className="num text-caption text-ink-3">
        {text[second]}
      </p>
    </div>
  )
}
