/**
 * The status pill of a claim (design system 11.2): an icon and a word, never colour alone. The word is the plain
 * label of the model's pill in the language shown, and `data-status` carries the engine's own word (APPROVED,
 * REFERRED, DECLINED, DISPUTE_OPEN) for the tests and for the receipt, which prints it in English.
 */
import { CircleCheck, CircleX, Clock, Hourglass, Scale, UserRound, type LucideIcon } from 'lucide-react'

import type { Pill, PillIcon, Tone } from '../hooks/trackerModel'
import { cn } from '../lib/cn'
import { t } from '../lib/copy'
import { useMiniapp } from '../shell/MiniappContext'
import { Badge } from '../ui/badge'

const ICONS: Readonly<Record<PillIcon, LucideIcon>> = { check: CircleCheck, clock: Clock, person: UserRound, x: CircleX, hourglass: Hourglass, scale: Scale }
const TONES: Readonly<Record<Tone, string>> = {
  paid: 'bg-paid-soft text-paid-ink',
  decided: 'bg-decided-soft text-decided',
  referred: 'bg-referred-soft text-referred-ink',
  blocked: 'bg-blocked-soft text-blocked',
  neutral: 'bg-secondary text-secondary-foreground',
}

export function ClaimPill({ pill, testId }: { pill: Pill; testId?: string }) {
  const { lang } = useMiniapp()
  const Icon = ICONS[pill.icon]
  return (
    <Badge variant="secondary" data-testid={testId} data-status={pill.word} className={cn('h-auto min-h-6 gap-1 py-1 text-left whitespace-normal', TONES[pill.tone])}>
      <Icon aria-hidden="true" />
      {t(pill.labelKey, lang)}
    </Badge>
  )
}
