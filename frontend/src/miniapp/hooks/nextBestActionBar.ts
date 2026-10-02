/**
 * The link between the rules and the bar (fs-04 section 12). A screen calls `useNextBest` with what it knows (its
 * name, the cover, the claims, the claim it shows, the buy state) once it is ready, or with null while it loads or has
 * failed: the rules of `nextBestAction` pick the sentence and the button, and the answer is registered with the bar
 * above the tab bar (`app-nba`, `data-nba` set to the rule id). The button leads where the target says: a screen
 * (perhaps a section through the hash, perhaps a control to focus once the screen has drawn it) or a control on this
 * screen. The dispute clock of the sentences comes from the rules, so the bar waits for `GET /api/policy`.
 */
import { useCallback } from 'react'
import { useNavigate } from 'react-router'

import { isFeatureEnabled } from '../../features'
import { t } from '../lib/copy'
import { useMiniapp } from '../shell/MiniappContext'
import { useNextBestAction } from '../shell/NextBestBar'
import { nextBestAction, type NbaInput, type NbaResult, type NbaTarget } from './nextBestAction'
import { useRules } from './useRules'

export type NextBestArgs = Omit<NbaInput, 'lang' | 'slaHours' | 'features'>

const FOCUS_WAIT_MS = 3_000

/** Moves focus to the control with this test id and scrolls it into view; false when it is not on the page. */
export function focusTestId(testId: string): boolean {
  const element = document.querySelector<HTMLElement>(`[data-testid="${testId}"]`)
  if (!element) return false
  element.scrollIntoView?.({ block: 'center' })
  element.focus()
  return true
}

/** Focuses a control that a screen is about to draw: now if it is there, else when it appears (for a moment only). */
export function focusWhenPresent(testId: string, waitMs = FOCUS_WAIT_MS): void {
  if (focusTestId(testId)) return
  const stop = (): void => {
    observer.disconnect()
    clearTimeout(timer)
  }
  const observer = new MutationObserver(() => {
    if (focusTestId(testId)) stop()
  })
  const timer = setTimeout(stop, waitMs)
  observer.observe(document.body, { childList: true, subtree: true })
}

export function useNextBest(args: NextBestArgs | null): NbaResult | null {
  const { lang, url } = useMiniapp()
  const navigate = useNavigate()
  const rules = useRules()
  const slaHours = rules.data?.dispute_sla_hours ?? null
  const result = args !== null && slaHours !== null ? nextBestAction({ ...args, lang, slaHours, features: { ask: isFeatureEnabled('n2_ask_chhatri'), slip: isFeatureEnabled('n3_slip_precheck') } }) : null

  const perform = useCallback(
    (target: NbaTarget): void => {
      if (target.type === 'focus') {
        focusTestId(target.testId)
        return
      }
      const link = url.href({
        screen: target.screen,
        ...(target.claim ? { claim: target.claim } : {}),
        ...(target.decision ? { decision: target.decision } : {}),
      })
      void navigate(target.section ? `${link}#${target.section}` : link)
      if (target.focus) focusWhenPresent(target.focus)
    },
    [url, navigate],
  )

  useNextBestAction(
    result === null
      ? null
      : {
          id: result.id,
          label: t(result.sentenceKey, lang, result.params),
          actionLabel: t(result.buttonKey, lang),
          onAction: () => perform(result.target),
        },
  )
  return result
}
