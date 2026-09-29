/**
 * Merchant Phone Page - WhatsApp-style interface (SPEC §20)
 */

import { useParams } from 'react-router'
import { useEffect, useState } from 'react'
import { apiClient } from '../api/client'
import type { MerchantDetail, Message } from '../api/types'

export default function Merchant() {
  const { id } = useParams<{ id: string }>()
  const [merchant, setMerchant] = useState<MerchantDetail | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      if (!id) return
      try {
        const [m, msgs] = await Promise.all([
          apiClient.get<MerchantDetail>(`/api/merchants/${id}`),
          apiClient.get<Message[]>(`/api/merchants/${id}/messages`),
        ])
        setMerchant(m)
        setMessages(msgs)
      } catch (err) {
        console.error('Failed to load merchant:', err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [id])

  if (loading) return <div className="p-8">Loading merchant...</div>
  if (!merchant) return <div className="p-8">Merchant not found</div>

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="bg-green-900 text-white p-4">
        <div className="font-bold">{merchant.shop_name}</div>
        <div className="text-sm text-green-200">Merchant protection · Hindi, English</div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 bg-gray-50 space-y-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.direction === 'OUTBOUND' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-xs rounded-lg p-3 ${
                msg.direction === 'OUTBOUND'
                  ? 'bg-green-100 text-black'
                  : 'bg-white text-black border'
              }`}
            >
              {msg.text_en && <div className="text-sm">{msg.text_en}</div>}
              {msg.text_hi && <div className="text-sm">{msg.text_hi}</div>}
              {msg.card && (
                <div className="bg-white rounded p-2 mt-2 border border-gray-300">
                  <div className="font-bold">{msg.card.amount_label}</div>
                  <div className="text-xs text-gray-600">{msg.card.subtitle_en}</div>
                </div>
              )}
              <div className="text-xs text-gray-500 mt-1">
                {new Date(msg.created_at).toLocaleTimeString()}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Input area */}
      <div className="bg-white border-t p-4">
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Message..."
            className="flex-1 border rounded px-3 py-2 text-sm"
          />
          <button className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
