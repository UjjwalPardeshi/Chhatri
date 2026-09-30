/** Routes (SPEC §20): / overview · /live map · /claims · /merchant/:id · /audit · /backtest · /policy. */
import { lazy, Suspense } from 'react'
import { BrowserRouter, Link, Route, Routes, useLocation } from 'react-router'

import type { Api } from './api/endpoints'
import { AppShell } from './components/layout/AppShell'
import { Loading } from './components/common/Status'
import { LiveProvider } from './state/live'

const Overview = lazy(() => import('./pages/Overview'))
const Live = lazy(() => import('./pages/Live'))
const Claims = lazy(() => import('./pages/Claims'))
const Merchant = lazy(() => import('./pages/Merchant'))
const Audit = lazy(() => import('./pages/Audit'))
const Backtest = lazy(() => import('./pages/Backtest'))
const Policy = lazy(() => import('./pages/Policy'))

function NotFound() {
  return (
    <div className="status-box">
      <span className="status-box__title">Page not found</span>
      <Link to="/">Back to the overview</Link>
    </div>
  )
}

/** While a page's chunk loads: the Overview's navy ground (no spinner on the landing page), a spinner elsewhere. */
export function RouteFallback() {
  const { pathname } = useLocation()
  return pathname === '/' ? <div className="ov-fallback" aria-busy="true" /> : <Loading />
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
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  )
}

export default function App({ api, mock }: { api: Api; mock: boolean }) {
  return (
    <BrowserRouter>
      <LiveProvider api={api} mock={mock}>
        <AppShell>
          <AppRoutes />
        </AppShell>
      </LiveProvider>
    </BrowserRouter>
  )
}
