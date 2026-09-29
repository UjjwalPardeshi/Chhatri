import { useEffect, useState } from 'react'
import { apiClient } from '../api/client'
import type { Case } from '../api/types'

export default function Claims() {
  const [cases, setCases] = useState<Case[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadCases = async () => {
      try {
        const data = await apiClient.get<Case[]>('/api/cases?status=')
        setCases(data)
      } catch (err) {
        console.error('Failed to load cases:', err)
      } finally {
        setLoading(false)
      }
    }

    loadCases()
  }, [])

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-6">Claims</h1>
      {loading ? (
        <p>Loading cases...</p>
      ) : cases.length === 0 ? (
        <p className="text-gray-600">No cases</p>
      ) : (
        <div className="space-y-4">
          {cases.map((c) => (
            <div key={c.id} className="bg-white p-4 rounded border">
              <div className="font-bold">{c.id}</div>
              <div className="text-gray-600">{c.merchant_name}</div>
              <div className="text-sm mt-2">Status: {c.status}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
