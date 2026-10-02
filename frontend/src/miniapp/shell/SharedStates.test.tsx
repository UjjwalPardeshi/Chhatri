/** The shared states of fs-04 section 7: every screen root says loading, empty, error, offline or ready in `data-state`. */
import { fireEvent, render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import type { MockBackend } from '../../mock/backend'
import { testApi } from '../../mock/testkit'
import { LiveProvider } from '../../state/live'
import type { Resource, ScreenState } from '../hooks/useResource'
import { MiniappProvider } from './MiniappContext'
import { ModeBadge, NetworkButton, ResourceScreen } from './SharedStates'

let backend: MockBackend
afterEach(() => {
  backend?.dispose()
  vi.restoreAllMocks()
})

function inApp(children: ReactNode, search = '?lang=en') {
  const kit = testApi()
  backend = kit.backend
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  return render(
    <MemoryRouter initialEntries={[`/merchant/S-0142/app${search}`]}>
      <LiveProvider api={kit.api} mock>
        <MiniappProvider merchantId="S-0142">{children}</MiniappProvider>
      </LiveProvider>
    </MemoryRouter>,
  )
}

function resource(state: ScreenState, patch: Partial<Resource<string>> = {}): Resource<string> {
  return { data: null, error: null, loading: false, reload: () => undefined, online: true, state, loadedAt: null, ...patch }
}

const Body = (data: string) => <p data-testid="body">{data}</p>

describe('ResourceScreen', () => {
  it('is a skeleton with aria-busy while loading, and no data', () => {
    inApp(<ResourceScreen name="claims" resource={resource('loading', { loading: true })}>{Body}</ResourceScreen>)
    const root = screen.getByTestId('screen-claims')
    expect(root.getAttribute('data-state')).toBe('loading')
    expect(root.getAttribute('aria-busy')).toBe('true')
    expect(screen.getByTestId('app-skeleton')).toBeTruthy()
    expect(screen.queryByTestId('body')).toBeNull()
  })

  it('is one sentence and the next action when empty', () => {
    inApp(
      <ResourceScreen name="claims" resource={resource('empty', { data: '' })} empty={<p data-testid="empty-copy">No claims yet.</p>}>
        {Body}
      </ResourceScreen>,
    )
    expect(screen.getByTestId('screen-claims').getAttribute('data-state')).toBe('empty')
    expect(screen.getByTestId('empty-copy').textContent).toBe('No claims yet.')
    expect(screen.getByTestId('screen-claims').getAttribute('aria-busy')).toBeNull()
  })

  it('is a plain sentence with the code in small text and a Retry that reloads, when it failed', () => {
    const reload = vi.fn<() => void>()
    const error = new ApiError('contract_violation', 'cover: unknown field surprise', 0)
    inApp(<ResourceScreen name="home" resource={resource('error', { error, reload })}>{Body}</ResourceScreen>)
    expect(screen.getByTestId('screen-home').getAttribute('data-state')).toBe('error')
    const alert = screen.getByTestId('app-error')
    expect(alert.getAttribute('role')).toBe('alert')
    expect(alert.textContent).toContain('Something went wrong. Try again.')
    expect(alert.textContent).toContain('Error code: contract_violation')
    fireEvent.click(screen.getByTestId('app-error-retry'))
    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('says "not found" for a 404, and shows no code for a network failure', () => {
    const notFound = new ApiError('not_found', 'decision D-999999 not found', 404)
    const view = inApp(<ResourceScreen name="receipt" resource={resource('error', { error: notFound })}>{Body}</ResourceScreen>)
    expect(screen.getByTestId('app-error').textContent).toContain('We could not find this.')
    view.unmount()
    const network = new ApiError('NETWORK_ERROR', 'offline', 0)
    inApp(<ResourceScreen name="receipt" resource={resource('error', { error: network })}>{Body}</ResourceScreen>)
    expect(screen.getByTestId('app-error').textContent).toContain('We cannot connect right now.')
    expect(screen.getByTestId('app-error').textContent).not.toContain('Error code')
  })

  it('keeps the last data under an offline banner that names the replay time', () => {
    inApp(
      <ResourceScreen name="home" resource={resource('offline', { data: 'last cover', loadedAt: '2025-08-22T17:05:00+05:30' })}>
        {Body}
      </ResourceScreen>,
    )
    expect(screen.getByTestId('screen-home').getAttribute('data-state')).toBe('offline')
    expect(screen.getByTestId('body').textContent).toBe('last cover')
    expect(screen.getByTestId('app-offline-banner').textContent).toMatch(/^Offline\. Showing data from .*17:05|5:05/)
  })

  it('is ready with the data', () => {
    inApp(<ResourceScreen name="home" resource={resource('ready', { data: 'cover' })}>{Body}</ResourceScreen>)
    expect(screen.getByTestId('screen-home').getAttribute('data-state')).toBe('ready')
    expect(screen.getByTestId('body').textContent).toBe('cover')
  })
})

describe('NetworkButton', () => {
  it('works while online', () => {
    const onClick = vi.fn<() => void>()
    inApp(<NetworkButton onClick={onClick}>Pay</NetworkButton>)
    fireEvent.click(screen.getByRole('button', { name: 'Pay' }))
    expect(onClick).toHaveBeenCalledTimes(1)
    expect(screen.queryByText(/needs the internet/)).toBeNull()
  })

  it('is disabled offline, with the reason beside it', () => {
    vi.spyOn(window.navigator, 'onLine', 'get').mockReturnValue(false)
    const onClick = vi.fn<() => void>()
    inApp(<NetworkButton onClick={onClick}>Pay</NetworkButton>)
    const button = screen.getByRole('button', { name: 'Pay' }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
    fireEvent.click(button)
    expect(onClick).not.toHaveBeenCalled()
    const reason = screen.getByText('This needs the internet. Please try again when you are online.')
    expect(button.getAttribute('aria-describedby')).toBe(reason.id)
  })
})

describe('ModeBadge', () => {
  it('prints the mode as the data says and never invents one', () => {
    inApp(
      <>
        <ModeBadge mode="SIMULATED" />
        <ModeBadge mode="FALLBACK" testId="fallback-badge" />
      </>,
    )
    expect(screen.getByTestId('app-mode-badge').textContent).toBe('SIMULATED')
    expect(screen.getByTestId('app-mode-badge').getAttribute('data-mode')).toBe('SIMULATED')
    expect(screen.getByTestId('fallback-badge').textContent).toBe('FALLBACK')
  })
})
