/**
 * Presenter mode controls (fs-08 12.2, design system 8.2): the "Present" toggle in the header (`aria-pressed`, the word
 * never changes) and, while the mode is on, a "Keys" button that opens the list of single-key shortcuts. The list is
 * also `?`, and Esc closes it. W (the what-if drawer) joins the list while the h24_whatif flag is on.
 */
import { useEffect, useRef, type MouseEvent as ReactMouseEvent } from 'react'

import { isFeatureEnabled } from '../../features'
import { usePresenter } from '../../state/presenter'

/** The shortcuts of fs-08 12.3 as the list shows them (the plain-words column is console copy, English only). */
export const PRESENTER_KEYS: readonly { keys: string; does: string }[] = Object.freeze([
  { keys: 'P', does: 'Turn presenter mode off' },
  { keys: 'Space', does: 'Play or Pause' },
  { keys: '1 to 4', does: 'Jump to a chapter, a minute before it' },
  { keys: 'S', does: 'Slow near payout on or off' },
  { keys: '?', does: 'Show this list' },
  { keys: 'Esc', does: 'Close this list or the More menu' },
])

/**
 * A mouse click leaves the focus on the button, and Space then presses that button again (the shortcuts stand aside for
 * a focused button), which would switch the mode off or close the list on the presenter's next keystroke. A pointer
 * click (`detail` above 0) hands the focus back to the page; a keyboard activation keeps it where the person is.
 */
function releaseFocusAfterPointer(event: ReactMouseEvent<HTMLButtonElement>): void {
  if (event.detail > 0) event.currentTarget.blur()
}

/** The list as shown: W joins it, before `?`, while the what-if drawer exists (flag h24_whatif). */
function visibleKeys(): readonly { keys: string; does: string }[] {
  if (!isFeatureEnabled('h24_whatif')) return PRESENTER_KEYS
  const at = PRESENTER_KEYS.findIndex((row) => row.keys === '?')
  return [...PRESENTER_KEYS.slice(0, at), { keys: 'W', does: 'Open or close the what-if drawer on the live map' }, ...PRESENTER_KEYS.slice(at)]
}

function KeyList() {
  return (
    <section id="presenter-keys" className="presenter-keys__list card" aria-label="Presenter keys">
      <dl>
        {visibleKeys().map((row) => (
          <div key={row.keys}>
            <dt>
              <kbd className="presenter-key">{row.keys}</kbd>
            </dt>
            <dd>{row.does}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

/** The "Present" toggle in the header. */
export function PresentButton() {
  const { on, toggle } = usePresenter()
  return (
    <button
      type="button"
      className="present-toggle"
      aria-pressed={on}
      onClick={(event) => {
        toggle()
        releaseFocusAfterPointer(event)
      }}
    >
      Present
    </button>
  )
}

/**
 * The "Keys" button and its list, in the replay controls while the mode is on (the header has no width to spare once
 * "Present" joins the integration chip and the sound toggle, and these are the keys of those controls).
 */
export function PresenterKeysButton() {
  const { on, keysOpen, setKeysOpen } = usePresenter()
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!keysOpen) return undefined
    const close = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setKeysOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [keysOpen, setKeysOpen])

  if (!on) return null
  return (
    <div className="presenter-keys" ref={rootRef}>
      <button
        type="button"
        className="btn"
        aria-expanded={keysOpen}
        aria-controls="presenter-keys"
        onClick={(event) => {
          setKeysOpen(!keysOpen)
          releaseFocusAfterPointer(event)
        }}
      >
        Keys
      </button>
      {keysOpen ? <KeyList /> : null}
    </div>
  )
}
