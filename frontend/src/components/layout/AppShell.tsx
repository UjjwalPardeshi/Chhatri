/** Page frame (SPEC §20): header, replay controls (live pages), routed page, attribution footer. */
import { useEffect, useState, type ReactNode } from 'react'
import { useLocation } from 'react-router'

import { useLive, useLiveEvent } from '../../state/live'
import { ControlBar } from './ControlBar'
import { Footer } from './Footer'
import { Header } from './Header'

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

export function AppShell({ children }: { children: ReactNode }) {
  const openCases = useOpenCaseCount()
  const { pathname } = useLocation()
  /** The Overview tells the story; the replay controls belong to the live pages. */
  const overview = pathname === '/'
  return (
    <div className={`app ${overview ? 'app--overview' : ''}`}>
      <Header openCases={openCases} />
      {overview ? null : <ControlBar />}
      <main className="app-main">{children}</main>
      <Footer />
    </div>
  )
}
