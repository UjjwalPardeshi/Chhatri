/**
 * Routes (SPEC §20): / overview · /live map · /claims · /merchant/:id · /audit · /backtest · /policy, and
 * /merchant/:id/app, the merchant mini-app full screen (fs-04 4.2): a second route tree inside LiveProvider and
 * outside AppShell, loaded lazily, and a redirect to /merchant/:id while the flag n1_miniapp is off.
 */
import { lazy, Suspense } from 'react'
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation, useParams } from 'react-router'

import type { Api } from './api/endpoints'
import { AppShell } from './components/layout/AppShell'
import { Loading } from './components/common/Status'
import { isFeatureEnabled } from './features'
import { LiveProvider } from './state/live'

const Overview = lazy(() => import('./pages/Overview'))
const Live = lazy(() => import('./pages/Live'))
const Claims = lazy(() => import('./pages/Claims'))
const Merchant = lazy(() => import('./pages/Merchant'))
const Audit = lazy(() => import('./pages/Audit'))
const Backtest = lazy(() => import('./pages/Backtest'))
const Policy = lazy(() => import('./pages/Policy'))
const Evals = lazy(() => import('./pages/Evals'))
const StandaloneRoute = lazy(() => import('./miniapp/shell/StandaloneRoute'))

function NotFound() {
  return (
    <div className="status-box">
      <span className="status-box__title">Page not found</span>
      <Link to="/">Back to the overview</Link>
    </div>
  )
}

/** While a page's chunk loads: the landing page's white ground with one quiet line (no spinner there), a spinner and a line elsewhere. */
export function RouteFallback() {
  const { pathname } = useLocation()
  return pathname === '/' ? (
    <div className="ov-fallback" aria-busy="true">
      <p className="ov-fallback__text">Loading Chhatri…</p>
    </div>
  ) : (
    <Loading label="Loading the page…" />
  )
}

export function AppRoutes() {
  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/live" element={<Live />} />
        <Route path="/claims" element={<Claims />} />
        <Route path="/merchant/:id" element={<Merchant />} />
        <Route path="/audit" element={<Audit />} />
        <Route path="/backtest" element={<Backtest />} />
        <Route path="/policy" element={<Policy />} />
        {isFeatureEnabled('h25_evals') ? <Route path="/evals" element={<Evals />} /> : null}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  )
}

/** The console's own query parameters, the only ones a redirect out of the mini-app keeps. */
const CONSOLE_PARAMS = ['mock', 'presenter'] as const

function consoleSearch(search: string): string {
  const current = new URLSearchParams(search)
  const kept = new URLSearchParams()
  for (const key of CONSOLE_PARAMS) {
    const value = current.get(key)
    if (value !== null) kept.set(key, value)
  }
  const query = kept.toString()
  return query ? `?${query}` : ''
}

/** `/merchant/:id/app`: the mini-app without the console around it. Off, it goes back to the merchant page and its chunk is never requested. */
function StandaloneApp() {
  const { id = '' } = useParams()
  const { search } = useLocation()
  if (!isFeatureEnabled('n1_miniapp')) return <Navigate to={`/merchant/${id}${consoleSearch(search)}`} replace />
  return (
    <Suspense
      fallback={
        <div aria-busy="true" style={{ minHeight: '100dvh' }}>
          <Loading label="Loading the app…" />
        </div>
      }
    >
      <StandaloneRoute />
    </Suspense>
  )
}

/** Both route trees: the mini-app on its own, and every console page inside the shell. */
export function AppTree() {
  return (
    <Routes>
      <Route path="/merchant/:id/app" element={<StandaloneApp />} />
      <Route
        path="*"
        element={
          <AppShell>
            <AppRoutes />
          </AppShell>
        }
      />
    </Routes>
  )
}

export default function App({ api, mock }: { api: Api; mock: boolean }) {
  return (
    <BrowserRouter>
      <LiveProvider api={api} mock={mock}>
        <AppTree />
      </LiveProvider>
    </BrowserRouter>
  )
}
