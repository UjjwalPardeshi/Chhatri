/**
 * Small parts the three rights screens share: the translator of the rights copy (`tr`), a sentence that may hold other
 * sentences (the time left), the heading level (the console's page owns the `h1`), and the next-best bar for a screen
 * whose rule is not one of the Wave 1 rules in `nextBestAction.ts` (the bar still carries one sentence and one button,
 * with `data-nba` set to the rule id).
 */
import { useNavigate } from 'react-router'

import { tr, type RightsCopyKey, type RightsCopyParams } from '../copy/rights'
import type { Lang } from '../lib/lang'
import { useMiniapp } from '../shell/MiniappContext'
import { useNextBestAction } from '../shell/NextBestBar'
import type { Line } from './grievanceModel'
import type { ReactNode } from 'react'

/** A sentence with its nested sentences filled in (the time left inside "Answer due in {time_left}"). */
export function lineText(line: Line, lang: Lang): string {
  const nested: Record<string, string> = {}
  for (const [name, inner] of Object.entries(line.nested ?? {})) nested[name] = lineText(inner, lang)
  return tr(line.key, lang, { ...line.params, ...nested })
}

export function Heading({ children, testId }: { children: ReactNode; testId?: string }) {
  const { embedded } = useMiniapp()
  const Title = embedded ? 'h3' : 'h2'
  return (
    <Title data-testid={testId} className="text-md font-medium">
      {children}
    </Title>
  )
}

export type RightsNba = { id: string; sentence: RightsCopyKey; button: RightsCopyKey; params?: RightsCopyParams; onAction: () => void }

/** Registers the bar of a rights screen, or none (null) while the screen loads or has failed. */
export function useRightsNba(nba: RightsNba | null): void {
  const { lang } = useMiniapp()
  useNextBestAction(nba === null ? null : { id: nba.id, label: tr(nba.sentence, lang, nba.params), actionLabel: tr(nba.button, lang), onAction: nba.onAction })
}

/** `go(screen, state)`: a link to another screen of the app that also carries a hint (the complaint topic, the chosen purpose). */
export function useGoWithState(): (href: string, state?: Record<string, string>) => void {
  const navigate = useNavigate()
  return (href, state) => void navigate(href, state ? { state } : undefined)
}
