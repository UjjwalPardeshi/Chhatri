/**
 * What would have changed the result (fs-04 10.4, H14). The engine writes each sentence from fixed templates and the
 * decision's own facts, so the card shows `text_hi` or `text_en` exactly as received and builds nothing in the
 * browser. The footer is always under them so they are not read as a promise. No sentence, no card.
 */
import { Lightbulb } from 'lucide-react'

import type { Counterfactual } from '../../api/types'
import { t } from '../lib/copy'
import { cn } from '../lib/cn'
import { useMiniapp } from '../shell/MiniappContext'
import { langAttr, pickBilingual } from './StepperLine'

type CardProps = {
  items: readonly Counterfactual[]
  testId: string
  /** On the receipt the row label is the title, so the card leaves its own out. */
  untitled?: boolean
  className?: string
}

export function CounterfactualCard({ items, testId, untitled = false, className }: CardProps) {
  const { lang } = useMiniapp()
  if (items.length === 0) return null
  return (
    <section data-kind={items[0].kind} className={cn('flex flex-col gap-2 rounded-lg border bg-accent p-4', className)}>
      {untitled ? null : (
        <h3 className="flex items-center gap-2 text-md font-medium text-accent-foreground">
          <Lightbulb className="size-4 shrink-0" aria-hidden="true" />
          {t('CF_TITLE', lang)}
        </h3>
      )}
      <div data-testid={testId} className="flex flex-col gap-2">
        {items.map((item) => {
          const shown = pickBilingual(lang, item.text_hi, item.text_en)
          return shown === null ? null : (
            <p key={item.id} lang={langAttr(shown.lang, lang)} className="text-sm leading-relaxed text-foreground">
              {shown.text}
            </p>
          )
        })}
      </div>
      <p className="text-caption text-ink-3">{t('CF_FOOTER', lang)}</p>
    </section>
  )
}
