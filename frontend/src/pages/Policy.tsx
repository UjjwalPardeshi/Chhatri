/**
 * Policy Page - Rules and decision authority (SPEC §20)
 */

import { useEffect, useState } from 'react'
import { apiClient } from '../api/client'
import type { PolicyView } from '../api/types'

export default function Policy() {
  const [policy, setPolicy] = useState<PolicyView | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const data = await apiClient.get<PolicyView>('/api/policy')
        setPolicy(data)
      } catch (err) {
        console.error('Failed to load policy:', err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) return <div className="p-8">Loading Policy...</div>

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-6">Policy</h1>

      {policy && (
        <>
          <div className="mb-8">
            <h2 className="text-xl font-bold mb-4">Decision Authority</h2>
            <table className="w-full border-collapse border">
              <thead className="bg-gray-100">
                <tr>
                  <th className="border p-2">Case</th>
                  <th className="border p-2">Alone</th>
                  <th className="border p-2">Human</th>
                </tr>
              </thead>
              <tbody>
                {policy.authority.map((row, idx) => (
                  <tr key={idx}>
                    <td className="border p-2">{row.case}</td>
                    <td className="border p-2">{row.alone}</td>
                    <td className="border p-2">{row.human}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div>
            <h2 className="text-xl font-bold mb-4">Checks</h2>
            <table className="w-full border-collapse border">
              <thead className="bg-gray-100">
                <tr>
                  <th className="border p-2">Code</th>
                  <th className="border p-2">Severity</th>
                  <th className="border p-2">Applies</th>
                </tr>
              </thead>
              <tbody>
                {policy.checks.slice(0, 10).map((check, idx) => (
                  <tr key={idx}>
                    <td className="border p-2">{check.code}</td>
                    <td className="border p-2">{check.severity}</td>
                    <td className="border p-2">{check.applies}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
