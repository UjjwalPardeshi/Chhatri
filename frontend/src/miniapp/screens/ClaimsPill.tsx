/**
 * The status pill of a claim (design system 11.2): an icon and a word, never colour alone. The word is the plain
 * label of the model's pill in the language shown, and `data-status` carries the engine's own word (APPROVED,
 * REFERRED, DECLINED, DISPUTE_OPEN) for the tests and for the receipt, which prints it in English.
 */
import type { Pill } from '../hooks/trackerModel'
import { t } from '../lib/copy'
import { StatusWord } from '../components/StatusWord'
import { useMiniapp } from '../shell/MiniappContext'

export function ClaimPill({ pill, testId }: { pill: Pill; testId?: string }) {
  const { lang } = useMiniapp()
  return (
    <StatusWord tone={pill.tone} data-testid={testId} data-status={pill.word} className="shrink-0 text-right">
      {t(pill.labelKey, lang)}
    </StatusWord>
  )
}
