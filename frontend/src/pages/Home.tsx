import { useEffect, useState } from 'react'
import { apiClient } from '../api/client'
import type { StateSnapshot } from '../api/types'

export default function Home() {
  const [state, setState] = useState<StateSnapshot | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadState = async () => {
      try {
        const data = await apiClient.get<StateSnapshot>('/api/state')
        setState(data)
      } catch (err) {
        console.error('Failed to load state:', err)
      } finally {
        setLoading(false)
      }
    }

    loadState()
    const interval = setInterval(loadState, 5000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return <div className="p-8">Loading map...</div>
  }

  if (!state) {
    return <div className="p-8">Failed to load state</div>
  }

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="bg-white border-b p-4">
        <div className="flex items-center justify-between">
          <div className="text-2xl font-bold">Chhatri</div>
          <div className="text-gray-600">{state.clock.label}</div>
          <div className="text-sm text-gray-500">
            {state.clock.running ? 'Running' : 'Paused'}
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex gap-4 p-4">
        {/* Map area (placeholder) */}
        <div className="flex-1 bg-blue-50 rounded border-2 border-blue-200 flex items-center justify-center">
          <div className="text-center">
            <div className="text-xl font-semibold text-blue-900">Live Map</div>
            <div className="text-blue-700 mt-2">Mumbai monsoon replay</div>
            <div className="text-blue-600 mt-4 text-sm">
              Zones triggered: {state.kpis.zones_triggered}
            </div>
            <div className="text-blue-600 text-sm">Shops paid: {state.kpis.shops_paid}</div>
          </div>
        </div>

        {/* Right panel */}
        <div className="w-80 space-y-4">
          {/* Zone card */}
          {state.zones.find((z) => z.status === 'triggered') && (
            <div className="bg-white rounded-lg shadow p-4 border-l-4 border-red-600">
              <div className="font-bold text-lg">
                {state.zones.find((z) => z.status === 'triggered')?.label}
              </div>
              <div className="mt-2 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span>Status:</span>
                  <span className="font-semibold text-red-600">TRIGGERED</span>
                </div>
              </div>
            </div>
          )}

          {/* KPIs */}
          <div className="grid grid-cols-3 gap-2">
            <div className="bg-white rounded p-3 text-center border">
              <div className="text-2xl font-bold">{state.kpis.zones_triggered}</div>
              <div className="text-xs text-gray-600">Zones triggered</div>
            </div>
            <div className="bg-white rounded p-3 text-center border">
              <div className="text-2xl font-bold">{state.kpis.shops_paid}</div>
              <div className="text-xs text-gray-600">Shops paid</div>
            </div>
            <div className="bg-white rounded p-3 text-center border">
              <div className="text-2xl font-bold">
                {state.kpis.trigger_to_money_min || '-'}
              </div>
              <div className="text-xs text-gray-600">min</div>
            </div>
          </div>

          {/* Explanation */}
          <div className="bg-blue-50 rounded p-4 text-sm text-blue-900">
            <div className="font-semibold mb-2">Why Zone 9 got nothing</div>
            <p>{state.explanations['Z9']}</p>
          </div>

          {/* Feed */}
          <div className="bg-white rounded-lg shadow p-4">
            <div className="font-bold mb-2">Live Feed</div>
            <div className="space-y-2 max-h-60 overflow-y-auto text-xs">
              {state.feed.map((item) => (
                <div key={item.id} className="border-b pb-1">
                  <div className="text-gray-600">{item.at}</div>
                  <div className="text-gray-900">{item.text_en}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
