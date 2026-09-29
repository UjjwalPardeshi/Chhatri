import { useEffect, useState } from 'react'
import React from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router'
import { apiClient } from './api/client'
import { sseStream } from './api/stream'
import type { SessionData } from './api/types'

// Import pages
const HomePage = React.lazy(() => import('./pages/Home'))
const ClaimsPage = React.lazy(() => import('./pages/Claims'))
const MerchantPage = React.lazy(() => import('./pages/Merchant'))
const AuditPage = React.lazy(() => import('./pages/Audit'))
const BacktestPage = React.lazy(() => import('./pages/Backtest'))
const PolicyPage = React.lazy(() => import('./pages/Policy'))

function App() {
  const [sessionLoading, setSessionLoading] = useState(true)

  useEffect(() => {
    // Initialize session if in demo mode
    const initSession = async () => {
      try {
        const session = await apiClient.get<SessionData>('/api/session').catch(() => null)
        if (session?.officer_token) {
          apiClient.setToken(session.officer_token)
          sseStream.setToken(session.officer_token)
        }
      } catch {
        // Not in demo mode or session failed
      } finally {
        setSessionLoading(false)
      }
    }

    initSession()
  }, [])

  if (sessionLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="text-2xl font-bold mb-2">Chhatri</div>
          <div className="text-gray-600">Initializing...</div>
        </div>
      </div>
    )
  }

  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        <React.Suspense
          fallback={
            <div className="flex items-center justify-center min-h-screen">
              <div>Loading...</div>
            </div>
          }
        >
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/claims" element={<ClaimsPage />} />
            <Route path="/merchant/:id" element={<MerchantPage />} />
            <Route path="/audit" element={<AuditPage />} />
            <Route path="/backtest" element={<BacktestPage />} />
            <Route path="/policy" element={<PolicyPage />} />
          </Routes>
        </React.Suspense>
      </div>
    </Router>
  )
}

export default App
