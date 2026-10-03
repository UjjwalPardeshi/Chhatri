/**
 * The screens of fs-04 section 4.4 and where each one lives: its tab, its title, the screen Back leads to, and the
 * component that draws it. Every screen of Wave 1 is here (cards 3.9 to 3.11); nothing else in the shell changes. A
 * screen of another spec that is not built yet is not in this list, so its link shows Home.
 */
import type { ComponentType } from 'react'

import type { CopyKey } from '../copy/en'
import type { Screen } from '../hooks/useMiniappUrl'
import { Ask } from './Ask'
import { Buy } from './Buy'
import { ConsentActivity } from './ConsentActivity'
import { Consents } from './Consents'
import { Coverage } from './Coverage'
import { Grievances } from './Grievances'
import { Help } from './Help'
import { Language } from './Language'
import { Home } from './Home'
import { ClaimDetail } from './ClaimDetail'
import { Claims } from './Claims'
import { Why } from './Why'
import { Receipt } from './Receipt'
import { SlipPrecheck } from './SlipPrecheck'

export type Tab = 'home' | 'claims' | 'help'

export type ScreenDef = { tab: Tab; titleKey: CopyKey; parent: Screen | null; Component: ComponentType }

export const SCREEN_DEFS: Readonly<Record<Screen, ScreenDef>> = {
  // The brand, not "Your cover": the cover card right under the app bar carries that heading.
  home: { tab: 'home', titleKey: 'app.name', parent: null, Component: Home },
  coverage: { tab: 'home', titleKey: 'explain.title', parent: 'home', Component: Coverage },
  buy: { tab: 'home', titleKey: 'buy.title', parent: 'home', Component: Buy },
  claims: { tab: 'claims', titleKey: 'tracker.title', parent: null, Component: Claims },
  claim: { tab: 'claims', titleKey: 'tracker.title', parent: 'claims', Component: ClaimDetail },
  why: { tab: 'claims', titleKey: 'why.title', parent: 'claims', Component: Why },
  receipt: { tab: 'claims', titleKey: 'receipt.title', parent: 'claims', Component: Receipt },
  help: { tab: 'help', titleKey: 'nav.help', parent: null, Component: Help },
  settings: { tab: 'help', titleKey: 'settings.title', parent: 'help', Component: Language },
  ask: { tab: 'help', titleKey: 'ask.title', parent: 'help', Component: Ask },
  grievances: { tab: 'help', titleKey: 'grv.title', parent: 'help', Component: Grievances },
  consents: { tab: 'help', titleKey: 'consent.title', parent: 'help', Component: Consents },
  'consent-activity': { tab: 'help', titleKey: 'activity.title', parent: 'consents', Component: ConsentActivity },
  slip: { tab: 'home', titleKey: 'SLIP_SHEET_TITLE', parent: 'home', Component: SlipPrecheck },
}

export const TABS: readonly { tab: Tab; screen: Screen; labelKey: CopyKey }[] = [
  { tab: 'home', screen: 'home', labelKey: 'nav.home' },
  { tab: 'claims', screen: 'claims', labelKey: 'nav.claims' },
  { tab: 'help', screen: 'help', labelKey: 'nav.help' },
]
