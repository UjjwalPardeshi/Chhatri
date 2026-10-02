/**
 * URL state of the mini-app (fs-04 section 4.3). Every move inside the app is a change of the query string, so a deep
 * link and the browser's Back button work without a nested router. `mock` and `presenter` (the console's own
 * parameters) are kept on every link the app builds; everything else is dropped. An unknown `screen` shows `home`
 * (a screen of another spec, or one behind a flag that is off, is unknown until it exists), and an id that does not
 * match its pattern is null, so a screen shows its not-found state instead of asking the API about it.
 */
import { useCallback, useMemo } from 'react'
import { useLocation, useNavigate } from 'react-router'

import { assertMerchantId } from '../../api/endpoints'
import { isFeatureEnabled } from '../../features'
import { isLang, type Lang } from '../lib/lang'

export const SCREENS = ['home', 'coverage', 'buy', 'claims', 'claim', 'why', 'receipt', 'help', 'settings', 'slip', 'ask', 'grievances', 'consents', 'consent-activity'] as const
export type Screen = (typeof SCREENS)[number]

const DECISION_ID = /^D-\d{6,}$/
const CLAIM_ID = /^CL-\d{6,}$/
/** The console's own parameters, kept on every link in this order. */
const KEPT_PARAMS = ['mock', 'presenter'] as const

export type MiniappLocation = { screen: Screen; claim: string | null; decision: string | null; lang: Lang | null }
export type NavTarget = { screen: Screen; claim?: string; decision?: string; lang?: Lang }
export type GoOptions = { replace?: boolean }

function isScreen(value: string | null): value is Screen {
  if (value === 'slip') return isFeatureEnabled('n3_slip_precheck')
  if (value === 'ask') return isFeatureEnabled('n2_ask_chhatri')
  if (value === 'grievances') return isFeatureEnabled('n5_grievances')
  if (value === 'consents' || value === 'consent-activity') return isFeatureEnabled('n6_consents')
  return value !== null && (SCREENS as readonly string[]).includes(value)
}

const matching = (value: string | null, pattern: RegExp): string | null => (value !== null && pattern.test(value) ? value : null)

export function parseMiniappSearch(search: string): MiniappLocation {
  const params = new URLSearchParams(search)
  const screen = params.get('screen')
  const lang = params.get('lang')
  return {
    screen: isScreen(screen) ? screen : 'home',
    claim: matching(params.get('claim'), CLAIM_ID),
    decision: matching(params.get('decision'), DECISION_ID),
    lang: isLang(lang) ? lang : null,
  }
}

/** `claim` goes with `screen=claim`, `decision` with `why` and `receipt`; Home carries no `screen`. */
export function miniappHref(pathname: string, search: string, target: NavTarget): string {
  if (target.claim !== undefined && !CLAIM_ID.test(target.claim)) throw new Error(`claim id ${target.claim} must look like CL-000142`)
  if (target.decision !== undefined && !DECISION_ID.test(target.decision)) throw new Error(`decision id ${target.decision} must look like D-000142`)
  const current = new URLSearchParams(search)
  const next = new URLSearchParams()
  for (const key of KEPT_PARAMS) {
    const value = current.get(key)
    if (value !== null) next.set(key, value)
  }
  const lang = target.lang ?? parseMiniappSearch(search).lang
  if (lang) next.set('lang', lang)
  if (target.screen !== 'home') next.set('screen', target.screen)
  if (target.screen === 'claim' && target.claim) next.set('claim', target.claim)
  if ((target.screen === 'why' || target.screen === 'receipt') && target.decision) next.set('decision', target.decision)
  const query = next.toString()
  return query ? `${pathname}?${query}` : pathname
}

/** The merchant id of the path, checked by the console's `assertMerchantId`; null for a bad one ("Unknown merchant"). */
export function merchantIdFromPath(raw: string | undefined): string | null {
  try {
    return raw ? assertMerchantId(raw) : null
  } catch {
    return null
  }
}

export type MiniappUrl = MiniappLocation & {
  href: (target: NavTarget) => string
  go: (target: NavTarget, options?: GoOptions) => void
  back: () => void
}

export function useMiniappUrl(): MiniappUrl {
  const { pathname, search } = useLocation()
  const navigate = useNavigate()
  const parsed = useMemo(() => parseMiniappSearch(search), [search])
  const href = useCallback((target: NavTarget) => miniappHref(pathname, search, target), [pathname, search])
  const go = useCallback((target: NavTarget, options?: GoOptions) => void navigate(miniappHref(pathname, search, target), { replace: options?.replace === true }), [navigate, pathname, search])
  const back = useCallback(() => void navigate(-1), [navigate])
  return { ...parsed, href, go, back }
}
