/** Presenter mode (fs-08 section 12): the URL and the tab's storage, the flag, and the single-key shortcuts. */
import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, useNavigate } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { PRESENTER_STORAGE_KEY, PresenterProvider, presenterKeyAction, resolvePresenter, usePresenter, type StorageLike } from './presenter'

function memoryStorage(initial: Record<string, string> = {}): StorageLike & { map: Map<string, string> } {
  const map = new Map(Object.entries(initial))
  return {
    map,
    getItem: (name) => map.get(name) ?? null,
    setItem: (name, value) => void map.set(name, value),
    removeItem: (name) => void map.delete(name),
  }
}

/** A keydown as the browser delivers it, aimed at `target` (defaults to the page body). */
function key(name: string, init: Partial<Pick<KeyboardEvent, 'ctrlKey' | 'metaKey' | 'altKey' | 'repeat' | 'defaultPrevented'>> = {}, target: EventTarget = document.body) {
  return { key: name, ctrlKey: false, metaKey: false, altKey: false, repeat: false, defaultPrevented: false, target, ...init }
}

describe('resolvePresenter (the pattern of ?mock=1 in config.ts)', () => {
  it('turns on with ?presenter=1 and remembers it for the tab', () => {
    const storage = memoryStorage()
    expect(resolvePresenter('?presenter=1', storage)).toBe(true)
    expect(storage.map.get(PRESENTER_STORAGE_KEY)).toBe('1')
  })

  it('turns off with ?presenter=0 and forgets it', () => {
    const storage = memoryStorage({ [PRESENTER_STORAGE_KEY]: '1' })
    expect(resolvePresenter('?presenter=0', storage)).toBe(false)
    expect(storage.map.has(PRESENTER_STORAGE_KEY)).toBe(false)
  })

  it('keeps what the tab remembered when a link carries no parameter', () => {
    expect(resolvePresenter('', memoryStorage({ [PRESENTER_STORAGE_KEY]: '1' }))).toBe(true)
    expect(resolvePresenter('?case=C-2291', memoryStorage())).toBe(false)
    expect(resolvePresenter('?presenter=maybe', memoryStorage({ [PRESENTER_STORAGE_KEY]: '1' }))).toBe(true)
  })

  it('works without storage, and when storage throws', () => {
    expect(resolvePresenter('?presenter=1', null)).toBe(true)
    expect(resolvePresenter('', null)).toBe(false)
    const broken: StorageLike = {
      getItem: () => {
        throw new Error('blocked')
      },
      setItem: () => {
        throw new Error('blocked')
      },
      removeItem: () => {
        throw new Error('blocked')
      },
    }
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    expect(resolvePresenter('?presenter=1', broken)).toBe(true)
    expect(resolvePresenter('?presenter=0', broken)).toBe(false)
    expect(resolvePresenter('', broken)).toBe(false)
  })
})

describe('presenterKeyAction (fs-08 12.3)', () => {
  it('maps the keys of the list', () => {
    expect(presenterKeyAction(key('p'))).toEqual({ type: 'toggle' })
    expect(presenterKeyAction(key('P'))).toEqual({ type: 'toggle' })
    expect(presenterKeyAction(key(' '))).toEqual({ type: 'playPause' })
    expect(presenterKeyAction(key('s'))).toEqual({ type: 'slow' })
    expect(presenterKeyAction(key('w'))).toEqual({ type: 'whatif' })
    expect(presenterKeyAction(key('W'))).toEqual({ type: 'whatif' })
    expect(presenterKeyAction(key('?'))).toEqual({ type: 'keys' })
    expect(presenterKeyAction(key('Escape'))).toEqual({ type: 'close' })
    for (const n of [1, 2, 3, 4]) expect(presenterKeyAction(key(String(n)))).toEqual({ type: 'chapter', index: n - 1 })
  })

  it('ignores every other key, including 0 and 5 to 9', () => {
    for (const other of ['0', '5', '9', 'a', 'Enter', 'Tab', 'ArrowRight']) expect(presenterKeyAction(key(other))).toBeNull()
  })

  it('leaves browser and system shortcuts alone, and held keys', () => {
    expect(presenterKeyAction(key('p', { ctrlKey: true }))).toBeNull()
    expect(presenterKeyAction(key('s', { metaKey: true }))).toBeNull()
    expect(presenterKeyAction(key('1', { altKey: true }))).toBeNull()
    expect(presenterKeyAction(key('p', { repeat: true }))).toBeNull()
    expect(presenterKeyAction(key('Escape', { defaultPrevented: true }))).toBeNull()
  })

  it('never fires while focus is in a text field, a select or a textarea', () => {
    const text = document.createElement('input')
    const search = Object.assign(document.createElement('input'), { type: 'search' })
    const area = document.createElement('textarea')
    const select = document.createElement('select')
    const editable = Object.assign(document.createElement('div'), { contentEditable: 'true' })
    // happy-dom does not reflect contentEditable into isContentEditable
    Object.defineProperty(editable, 'isContentEditable', { value: true })
    for (const target of [text, search, area, select, editable]) {
      for (const name of ['p', ' ', '1', 's', '?', 'Escape']) expect(presenterKeyAction(key(name, {}, target))).toBeNull()
    }
  })

  it('lets a button keep Space, but not the other keys', () => {
    const button = document.createElement('button')
    const link = Object.assign(document.createElement('a'), { href: '#x' })
    const checkbox = Object.assign(document.createElement('input'), { type: 'checkbox' })
    for (const target of [button, link, checkbox]) {
      expect(presenterKeyAction(key(' ', {}, target))).toBeNull()
      expect(presenterKeyAction(key('2', {}, target))).toEqual({ type: 'chapter', index: 1 })
      expect(presenterKeyAction(key('s', {}, target))).toEqual({ type: 'slow' })
    }
  })
})

function Probe() {
  const presenter = usePresenter()
  const navigate = useNavigate()
  return (
    <div>
      <output data-testid="state">{`${presenter.available ? 'available' : 'unavailable'}|${presenter.on ? 'on' : 'off'}|${presenter.keysOpen ? 'keys' : 'nokeys'}`}</output>
      <button type="button" onClick={presenter.toggle}>
        toggle
      </button>
      <button type="button" onClick={() => navigate('/claims')}>
        go
      </button>
      <button type="button" onClick={() => navigate('/claims?presenter=0')}>
        go off
      </button>
      <input aria-label="type here" />
    </div>
  )
}

function renderProbe(entry = '/live') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <PresenterProvider>
        <Probe />
      </PresenterProvider>
    </MemoryRouter>,
  )
}
const state = () => screen.getByTestId('state').textContent

beforeEach(() => window.sessionStorage.clear())
afterEach(() => vi.unstubAllEnvs())

describe('PresenterProvider', () => {
  it('is off, and unavailable, while the console_polish flag is off, even with ?presenter=1', () => {
    vi.stubEnv('VITE_FEATURES', '')
    renderProbe('/live?presenter=1')
    expect(state()).toBe('unavailable|off|nokeys')
    expect(window.sessionStorage.getItem(PRESENTER_STORAGE_KEY)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'toggle' }))
    expect(state()).toBe('unavailable|off|nokeys')
  })

  it('is available but off by default when the flag is on', () => {
    vi.stubEnv('VITE_FEATURES', 'console_polish')
    renderProbe()
    expect(state()).toBe('available|off|nokeys')
  })

  it('turns on with ?presenter=1, keeps the mode through in-app links, and turns off with ?presenter=0', () => {
    vi.stubEnv('VITE_FEATURES', 'console_polish')
    renderProbe('/live?presenter=1')
    expect(state()).toBe('available|on|nokeys')
    expect(window.sessionStorage.getItem(PRESENTER_STORAGE_KEY)).toBe('1')
    fireEvent.click(screen.getByRole('button', { name: 'go' }))
    expect(state()).toBe('available|on|nokeys')
    fireEvent.click(screen.getByRole('button', { name: 'go off' }))
    expect(state()).toBe('available|off|nokeys')
    expect(window.sessionStorage.getItem(PRESENTER_STORAGE_KEY)).toBeNull()
  })

  it('starts on when the tab remembered it', () => {
    vi.stubEnv('VITE_FEATURES', 'console_polish')
    window.sessionStorage.setItem(PRESENTER_STORAGE_KEY, '1')
    renderProbe()
    expect(state()).toBe('available|on|nokeys')
  })

  it('toggles from the header button and remembers it', () => {
    vi.stubEnv('VITE_FEATURES', 'console_polish')
    renderProbe()
    fireEvent.click(screen.getByRole('button', { name: 'toggle' }))
    expect(state()).toBe('available|on|nokeys')
    expect(window.sessionStorage.getItem(PRESENTER_STORAGE_KEY)).toBe('1')
    fireEvent.click(screen.getByRole('button', { name: 'toggle' }))
    expect(state()).toBe('available|off|nokeys')
    expect(window.sessionStorage.getItem(PRESENTER_STORAGE_KEY)).toBeNull()
  })

  it('P turns it off while on, and does nothing while off (the keys exist only while on)', () => {
    vi.stubEnv('VITE_FEATURES', 'console_polish')
    renderProbe()
    fireEvent.keyDown(document.body, { key: 'p' })
    expect(state()).toBe('available|off|nokeys')
    fireEvent.click(screen.getByRole('button', { name: 'toggle' }))
    fireEvent.keyDown(document.body, { key: 'p' })
    expect(state()).toBe('available|off|nokeys')
    expect(window.sessionStorage.getItem(PRESENTER_STORAGE_KEY)).toBeNull()
  })

  it('opens the key list with ? and closes it with Esc, only while on', () => {
    vi.stubEnv('VITE_FEATURES', 'console_polish')
    renderProbe()
    fireEvent.keyDown(document.body, { key: '?' })
    expect(state()).toBe('available|off|nokeys')
    fireEvent.click(screen.getByRole('button', { name: 'toggle' }))
    fireEvent.keyDown(document.body, { key: '?' })
    expect(state()).toBe('available|on|keys')
    fireEvent.keyDown(document.body, { key: 'Escape' })
    expect(state()).toBe('available|on|nokeys')
    fireEvent.keyDown(document.body, { key: '?' })
    act(() => screen.getByRole('button', { name: 'toggle' }).click())
    expect(state()).toBe('available|off|nokeys')
  })

  it('ignores the keys while the focus is in an input', () => {
    vi.stubEnv('VITE_FEATURES', 'console_polish')
    renderProbe('/live?presenter=1')
    fireEvent.keyDown(screen.getByRole('textbox', { name: 'type here' }), { key: 'p' })
    fireEvent.keyDown(screen.getByRole('textbox', { name: 'type here' }), { key: '?' })
    expect(state()).toBe('available|on|nokeys')
  })

  it('stops listening for keys once it is off', () => {
    vi.stubEnv('VITE_FEATURES', 'console_polish')
    const add = vi.spyOn(document, 'addEventListener')
    const remove = vi.spyOn(document, 'removeEventListener')
    renderProbe('/live?presenter=1')
    const added = add.mock.calls.filter(([type]) => type === 'keydown')
    expect(added).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: 'toggle' }))
    expect(state()).toBe('available|off|nokeys')
    const removed = remove.mock.calls.filter(([type]) => type === 'keydown')
    expect(removed).toHaveLength(1)
    expect(removed[0][1]).toBe(added[0][1])
  })

  it('removes its key listener when it unmounts while on', () => {
    vi.stubEnv('VITE_FEATURES', 'console_polish')
    const remove = vi.spyOn(document, 'removeEventListener')
    const { unmount } = renderProbe('/live?presenter=1')
    unmount()
    expect(remove.mock.calls.filter(([type]) => type === 'keydown')).toHaveLength(1)
  })
})

function Bare() {
  const presenter = usePresenter()
  presenter.toggle()
  presenter.setKeysOpen(true)
  return <p>{`${presenter.available}|${presenter.on}|${presenter.keysOpen}`}</p>
}

describe('usePresenter outside a provider', () => {
  it('is inert: off, unavailable and quiet', () => {
    render(<Bare />)
    expect(screen.getByText('false|false|false')).toBeTruthy()
  })
})
