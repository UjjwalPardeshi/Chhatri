/**
 * Presenter mode (fs-08 section 12, design system 8.2) for the person presenting on a projector: the console
 * steps its type one rung up, folds the quiet replay controls under "More" and answers a few single-key
 * shortcuts. It writes nothing, calls no endpoint and removes no label. The mode lives behind the `console_polish`
 * flag. `?presenter=1` turns it on and `?presenter=0` off, remembered for the tab in sessionStorage so in-app
 * links keep it (the pattern of `?mock=1` in config.ts); storage is read and written inside try/catch and the page
 * works without it. The shortcuts are active only while the mode is on, so a viewer can always turn them off
 * (WCAG 2.1.4), and never while focus is in a field.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useLocation } from 'react-router'

import type { StorageLike } from '../config'
import { isFeatureEnabled } from '../features'

export type { StorageLike }

export const PRESENTER_STORAGE_KEY = 'chhatri.presenter'
const PARAM = 'presenter'

function tabStorage(): StorageLike | null {
  try {
    return window.sessionStorage
  } catch (error) {
    console.warn('[presenter] sessionStorage unavailable', error)
    return null
  }
}

function remember(storage: StorageLike | null, on: boolean): void {
  try {
    if (on) storage?.setItem(PRESENTER_STORAGE_KEY, '1')
    else storage?.removeItem(PRESENTER_STORAGE_KEY)
  } catch (error) {
    console.warn('[presenter] could not remember the mode for this tab', error)
  }
}

function recalled(storage: StorageLike | null): boolean {
  try {
    return storage?.getItem(PRESENTER_STORAGE_KEY) === '1'
  } catch (error) {
    console.warn('[presenter] could not read the mode of this tab', error)
    return false
  }
}

/** `?presenter=1` on, `?presenter=0` off (both remembered for the tab), anything else keeps what the tab remembered. */
export function resolvePresenter(search: string, storage: StorageLike | null): boolean {
  const param = new URLSearchParams(search).get(PARAM)
  if (param === '1' || param === '0') {
    remember(storage, param === '1')
    return param === '1'
  }
  return recalled(storage)
}

export type PresenterKeyAction = { type: 'toggle' } | { type: 'playPause' } | { type: 'slow' } | { type: 'whatif' } | { type: 'keys' } | { type: 'close' } | { type: 'chapter'; index: number }
export type PresenterKeyEvent = Pick<KeyboardEvent, 'key' | 'ctrlKey' | 'metaKey' | 'altKey' | 'repeat' | 'defaultPrevented' | 'target'>

/** Input types that take typed text: every key belongs to them. Checkboxes, radios and buttons are not text entry. */
const TEXT_INPUT_TYPES: ReadonlySet<string> = new Set(['text', 'search', 'email', 'url', 'tel', 'password', 'number', 'date', 'datetime-local', 'month', 'time', 'week'])
const TEXT_ROLES: ReadonlySet<string> = new Set(['textbox', 'searchbox', 'combobox', 'spinbutton'])
/** Controls that use Space themselves (activate, toggle, scroll a list): Space is theirs while one has focus. */
const SPACE_CONTROLS = 'button, a[href], summary, input, select, textarea, [role="button"], [role="checkbox"], [role="switch"], [role="menuitem"], [role="tab"], [role="link"], [role="option"]'

function isTextEntry(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  if (target instanceof HTMLInputElement) return TEXT_INPUT_TYPES.has(target.type)
  if (target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement) return true
  return target.isContentEditable || TEXT_ROLES.has(target.getAttribute('role') ?? '')
}

function spaceBelongsToControl(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && target.closest(SPACE_CONTROLS) !== null
}

/**
 * What a key press asks of the presenter (fs-08 12.3), or null when it asks nothing: modified or held keys, keys
 * typed into a field, and Space while a control that uses Space has focus are all left alone. Whether the mode is on
 * is the caller's business: nothing listens while it is off.
 */
export function presenterKeyAction(event: PresenterKeyEvent): PresenterKeyAction | null {
  if (event.ctrlKey || event.metaKey || event.altKey || event.repeat || event.defaultPrevented) return null
  if (isTextEntry(event.target)) return null
  switch (event.key) {
    case 'p':
    case 'P':
      return { type: 'toggle' }
    case ' ':
      return spaceBelongsToControl(event.target) ? null : { type: 'playPause' }
    case 's':
    case 'S':
      return { type: 'slow' }
    case 'w':
    case 'W':
      return { type: 'whatif' }
    case '?':
      return { type: 'keys' }
    case 'Escape':
      return { type: 'close' }
    case '1':
    case '2':
    case '3':
    case '4':
      return { type: 'chapter', index: Number(event.key) - 1 }
    default:
      return null
  }
}

export type PresenterValue = {
  /** The `console_polish` flag is on: the header offers the Present button. */
  available: boolean
  on: boolean
  setOn: (on: boolean) => void
  toggle: () => void
  /** The list of presenter keys is showing. */
  keysOpen: boolean
  setKeysOpen: (open: boolean) => void
}

const noop = () => undefined
const INERT: PresenterValue = Object.freeze({ available: false, on: false, setOn: noop, toggle: noop, keysOpen: false, setKeysOpen: noop })
const PresenterContext = createContext<PresenterValue>(INERT)

/** The presenter state; outside a provider (a part rendered alone) it is off, unavailable and inert. */
export function usePresenter(): PresenterValue {
  return useContext(PresenterContext)
}

export function PresenterProvider({ children }: { children: ReactNode }) {
  const { search } = useLocation()
  const available = isFeatureEnabled('console_polish')
  const [mode, setMode] = useState(() => ({ on: available && resolvePresenter(search, tabStorage()), search }))
  const [keysShown, setKeysShown] = useState(false)

  /** A new location: a link that names the mode (`?presenter=1` or `0`) sets it, every other link keeps it. */
  let current = mode
  if (mode.search !== search) {
    const param = new URLSearchParams(search).get(PARAM)
    current = { on: param === '1' || param === '0' ? param === '1' : mode.on, search }
    setMode(current)
  }
  const on = available && current.on

  /** The tab remembers the mode, so in-app links (and a reload) keep it. */
  useEffect(() => {
    if (available) remember(tabStorage(), on)
  }, [available, on])

  const setOn = useCallback(
    (next: boolean) => {
      if (!available) return
      setMode((previous) => ({ ...previous, on: next }))
      if (!next) setKeysShown(false)
    },
    [available],
  )
  const toggle = useCallback(() => setOn(!on), [on, setOn])

  /** P (off), ? and Esc belong to the mode itself; Space, 1 to 4 and S need the replay and are handled where it lives (ControlBar). */
  useEffect(() => {
    if (!on) return undefined
    const onKey = (event: KeyboardEvent) => {
      const action = presenterKeyAction(event)
      if (action?.type === 'toggle') {
        event.preventDefault()
        setOn(false)
      } else if (action?.type === 'keys') {
        event.preventDefault()
        setKeysShown(true)
      } else if (action?.type === 'close') {
        setKeysShown(false)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [on, setOn])

  const value = useMemo<PresenterValue>(
    () => ({ available, on, setOn, toggle, keysOpen: on && keysShown, setKeysOpen: setKeysShown }),
    [available, on, setOn, toggle, keysShown],
  )
  return <PresenterContext.Provider value={value}>{children}</PresenterContext.Provider>
}
