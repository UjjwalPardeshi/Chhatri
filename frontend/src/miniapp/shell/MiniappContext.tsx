/**
 * What every part of the mini-app shares: the merchant of the path, the language, the URL state, the replay clock and
 * whether the device is online (fs-04 sections 4, 6.3 and 13). Both entry points (the console frame and the standalone
 * route) mount one provider, so both read the same live state. The language is the URL's `lang`, else the one the
 * person chose last (kept in this browser), else the merchant's own, else Hindi; `mr` shows Hindi until Marathi ships.
 */
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

import type { MerchantDetail } from '../../api/types'
import { isFeatureEnabled } from '../../features'
import { useLive } from '../../state/live'
import type { AsyncState } from '../../state/useAsync'
import { useMerchant } from '../../state/useMerchant'
import { useMiniappUrl, type MiniappUrl } from '../hooks/useMiniappUrl'
import { useOnline } from '../hooks/useResource'
import { DEFAULT_LANG, isLang, type Lang } from '../lib/lang'

export const LANG_STORAGE_KEY = 'chhatri.miniapp.lang'

/** What the next-best bar shows: one sentence and one button. Card 3.11 decides which rule applies. */
export type NextBestAction = { id: string; label: string; actionLabel: string; onAction: () => void }

export type MiniappValue = {
  merchantId: string
  /** True inside the console's frame, where the console page already owns the `main` landmark and the page `h1`. */
  embedded: boolean
  lang: Lang
  setLang: (lang: Lang) => void
  url: MiniappUrl
  merchant: AsyncState<MerchantDetail>
  /** The replay clock, never the device clock. */
  now: string | null
  online: boolean
  mock: boolean
  nba: NextBestAction | null
  setNba: (action: NextBestAction | null) => void
}

type LangInput = { url: Lang | null; stored: Lang | null; merchant: string | null; marathi: boolean }

/** URL, then the stored choice, then the merchant's language, then Hindi; Marathi is Hindi while `n8_marathi` is off. */
export function resolveLang({ url, stored, merchant, marathi }: LangInput): Lang {
  const chosen = url ?? stored ?? (isLang(merchant) ? merchant : null) ?? DEFAULT_LANG
  return chosen === 'mr' && !marathi ? DEFAULT_LANG : chosen
}

function readStoredLang(): Lang | null {
  try {
    const value = window.localStorage.getItem(LANG_STORAGE_KEY)
    return isLang(value) ? value : null
  } catch {
    return null
  }
}

function storeLang(lang: Lang): void {
  try {
    window.localStorage.setItem(LANG_STORAGE_KEY, lang)
  } catch {
    // Storage is blocked: the language still switches for this session, because the URL carries it.
  }
}

const MiniappContext = createContext<MiniappValue | null>(null)

export function useMiniapp(): MiniappValue {
  const value = useContext(MiniappContext)
  if (!value) throw new Error('useMiniapp must be used inside <MiniappProvider>')
  return value
}

export function MiniappProvider({ merchantId, embedded = false, children }: { merchantId: string; embedded?: boolean; children: ReactNode }) {
  const { snapshot, mock } = useLive()
  const url = useMiniappUrl()
  const online = useOnline()
  const merchant = useMerchant(merchantId)
  const [nba, setNba] = useState<NextBestAction | null>(null)
  const lang = resolveLang({ url: url.lang, stored: readStoredLang(), merchant: merchant.data?.language ?? null, marathi: isFeatureEnabled('n8_marathi') })
  const { go, screen, claim, decision } = url
  const setLang = useCallback(
    (next: Lang) => {
      storeLang(next)
      go({ screen, ...(claim ? { claim } : {}), ...(decision ? { decision } : {}), lang: next }, { replace: true })
    },
    [go, screen, claim, decision],
  )
  const now = snapshot?.clock.now ?? null
  const value = useMemo<MiniappValue>(
    () => ({ merchantId, embedded, lang, setLang, url, merchant, now, online, mock, nba, setNba }),
    [merchantId, embedded, lang, setLang, url, merchant, now, online, mock, nba],
  )
  return <MiniappContext.Provider value={value}>{children}</MiniappContext.Provider>
}
