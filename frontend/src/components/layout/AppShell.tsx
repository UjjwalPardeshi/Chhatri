/** Page frame (SPEC §20): header, replay controls (live pages), routed page, attribution footer. */
import { useEffect, useState, type ReactNode } from 'react'
import { useLocation } from 'react-router'

import { useLive, useLiveEvent } from '../../state/live'
import { OpsProvider } from '../../state/ops'
import { PresenterProvider, usePresenter } from '../../state/presenter'
import { Feature } from '../common/Feature'
import { ControlBar } from './ControlBar'
import { Footer } from './Footer'
import { Header } from './Header'
import { OPS_STRIP_PATHS, OpsStrip } from './OpsStrip'

function useOpenCaseCount(): number {
  const { api, snapshot } = useLive()
  const [count, setCount] = useState(0)
  const [version, setVersion] = useState(0)
  const scenarioKey = `${snapshot?.clock.scenario}|${snapshot?.clock.start}`
  useLiveEvent(['case', 'scenario'], () => setVersion((v) => v + 1))
  useEffect(() => {
    const controller = new AbortController()
    api.cases('OPEN', controller.signal).then(
      (cases) => setCount(cases.length),
      (error: unknown) => {
        if (!controller.signal.aborted) console.warn('[shell] open case count unavailable', error)
      },
    )
    return () => controller.abort()
  }, [api, version, scenarioKey])
  return count
}

function Frame({ children }: { children: ReactNode }) {
  const openCases = useOpenCaseCount()
  const { pathname } = useLocation()
  const { on: presenting } = usePresenter()
  /** The Overview tells the story; the replay controls belong to the live pages. */
  const overview = pathname === '/'
  return (
    <OpsProvider active={OPS_STRIP_PATHS.includes(pathname)}>
      <div className={`app ${overview ? 'app--overview' : ''}`} data-presenter={presenting ? 'on' : undefined}>
        <Header openCases={openCases} />
        {overview ? null : (
          <Feature name="h8_ops_strip" fallback={<ControlBar />}>
            <div className="app-controls">
              <ControlBar />
              {/* On /live the strip is a band over the map column (Live.tsx), so the right panel keeps its height. */}
              {pathname === '/live' ? null : <OpsStrip />}
            </div>
          </Feature>
        )}
        <main className="app-main">{children}</main>
        <Footer />
      </div>
    </OpsProvider>
  )
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <PresenterProvider>
      <Frame>{children}</Frame>
    </PresenterProvider>
  )
}
