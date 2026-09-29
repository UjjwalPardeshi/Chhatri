/**
 * Backtest Page - Historical model comparison (SPEC §20)
 */

import { useEffect, useState } from 'react'
import { apiClient } from '../api/client'
import type { BacktestReport } from '../api/types'

export default function Backtest() {
  const [report, setReport] = useState<BacktestReport | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const data = await apiClient.get<BacktestReport>('/api/backtest')
        setReport(data)
      } catch (err) {
        console.error('Failed to load backtest:', err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) return <div className="p-8">Loading Backtest...</div>

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-6">Backtest Report</h1>
      {report && (
        <>
          <p className="text-gray-600 mb-4">{report.label}</p>
          <div className="grid grid-cols-2 gap-4">
            {report.triggers.map((t, i) => (
              <div key={i} className="bg-white rounded p-4 border">
                <h3 className="font-bold text-lg">{t.name}</h3>
                <div className="text-sm mt-2 space-y-1">
                  <div>Real drops paid: {t.real_drops_paid}/{t.real_drops}</div>
                  <div>Recall: {(t.recall * 100).toFixed(1)}%</div>
                  <div>False positive rate: {(t.false_positive_rate * 100).toFixed(1)}%</div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
