/**
 * Audit Page - Audit trail and verification (SPEC §20)
 */

import { useEffect, useState } from 'react'
import { apiClient } from '../api/client'
import type { AuditEntry, AuditVerify } from '../api/types'

export default function Audit() {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [verification, setVerification] = useState<AuditVerify | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const data = await apiClient.get<AuditEntry[]>('/api/audit?after=0&limit=200')
        setEntries(data)
      } catch (err) {
        console.error('Failed to load audit entries:', err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const handleVerify = async () => {
    try {
      const result = await apiClient.get<AuditVerify>('/api/audit/verify')
      setVerification(result)
    } catch (err) {
      console.error('Failed to verify chain:', err)
    }
  }

  if (loading) return <div className="p-8">Loading...</div>

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-6">Audit Log</h1>
      <button
        onClick={handleVerify}
        className="px-4 py-2 bg-blue-600 text-white rounded mb-6 hover:bg-blue-700"
      >
        Verify Chain
      </button>
      {verification && (
        <div
          className={`p-4 rounded mb-6 ${verification.valid ? 'bg-green-50' : 'bg-red-50'}`}
        >
          <div className={`font-bold ${verification.valid ? 'text-green-800' : 'text-red-800'}`}>
            {verification.valid ? '✓ Valid' : '✗ Invalid'}
          </div>
        </div>
      )}
      <table className="w-full border-collapse border">
        <thead className="bg-gray-100">
          <tr>
            <th className="border p-2">Seq</th>
            <th className="border p-2">At</th>
            <th className="border p-2">Action</th>
          </tr>
        </thead>
        <tbody>
          {entries.slice(0, 20).map((e) => (
            <tr key={e.seq}>
              <td className="border p-2">{e.seq}</td>
              <td className="border p-2 text-sm">{new Date(e.at).toLocaleString()}</td>
              <td className="border p-2">{e.action}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
