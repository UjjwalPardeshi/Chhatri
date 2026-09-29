/**
 * API Client Tests
 * Tests envelope parsing, error extraction, Bearer token handling
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ApiClient, ApiError } from './client'

describe('ApiClient', () => {
  let client: ApiClient
  const baseUrl = 'http://api.example.com'

  beforeEach(() => {
    client = new ApiClient(baseUrl)
    vi.clearAllMocks()
  })

  describe('setToken', () => {
    it('should set the Bearer token', () => {
      const token = 'test-token-123'
      client.setToken(token)
      // Token is used in subsequent requests (tested via fetch)
    })
  })

  describe('error envelope parsing', () => {
    it('should extract error message from error envelope', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: false,
        json: async () => ({
          ok: false,
          error: {
            code: 'VALIDATION_ERROR',
            message: 'Invalid merchant ID',
            fields: { merchant_id: 'Must be alphanumeric' },
          },
        }),
      })

      try {
        await client.get('/api/merchants/invalid')
        expect.fail('Should have thrown ApiError')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        expect((error as ApiError).message).toBe('Invalid merchant ID')
        expect((error as ApiError).code).toBe('VALIDATION_ERROR')
      }
    })

    it('should extract error.fields from error envelope', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: false,
        json: async () => ({
          ok: false,
          error: {
            code: 'VALIDATION_ERROR',
            message: 'Validation failed',
            fields: {
              merchant_id: 'Must be alphanumeric',
              amount_paise: 'Must be positive integer',
            },
          },
        }),
      })

      try {
        await client.post('/api/cases/C-123/approve', { note: '' })
        expect.fail('Should have thrown ApiError')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        const apiError = error as ApiError
        expect(apiError.fields).toEqual({
          merchant_id: 'Must be alphanumeric',
          amount_paise: 'Must be positive integer',
        })
      }
    })

    it('should handle error envelope with missing fields', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: false,
        json: async () => ({
          ok: false,
          error: {
            code: 'INTERNAL_ERROR',
            message: 'Server error occurred',
          },
        }),
      })

      try {
        await client.get('/api/state')
        expect.fail('Should have thrown ApiError')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        const apiError = error as ApiError
        expect(apiError.fields).toBeUndefined()
      }
    })
  })

  describe('successful envelope parsing', () => {
    it('should extract data from successful envelope', async () => {
      const mockData = { id: 'S-0142', shop_name: 'Anil Tea Stall' }
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ok: true,
          data: mockData,
        }),
      })

      const result = await client.get('/api/merchants/S-0142')
      expect(result).toEqual(mockData)
    })

    it('should handle pagination metadata', async () => {
      const mockData = [{ id: 'C-2291', merchant_id: 'S-0142' }]
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ok: true,
          data: mockData,
          meta: { total: 1, limit: 10, offset: 0 },
        }),
      })

      const result = await client.get('/api/cases?status=OPEN')
      expect(result).toEqual(mockData)
    })
  })

  describe('Bearer token header', () => {
    it('should include Authorization header when token is set', async () => {
      client.setToken('officer-token-xyz')

      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ok: true,
          data: { outcome: 'APPROVED' },
        }),
      })

      await client.post('/api/cases/C-2291/approve', { note: 'Verified' })

      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer officer-token-xyz',
          }),
        })
      )
    })

    it('should not include Authorization header when token is not set', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ok: true,
          data: { zones: [] },
        }),
      })

      await client.get('/api/geo/zones')

      const call = (global.fetch as any).mock.calls[0]
      expect(call[1].headers.Authorization).toBeUndefined()
    })
  })

  describe('HTTP error handling', () => {
    it('should handle HTTP 404 with error envelope', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({
          ok: false,
          error: {
            code: 'NOT_FOUND',
            message: 'Merchant not found',
          },
        }),
      })

      try {
        await client.get('/api/merchants/INVALID')
        expect.fail('Should have thrown ApiError')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        expect((error as ApiError).statusCode).toBe(404)
        expect((error as ApiError).code).toBe('NOT_FOUND')
      }
    })

    it('should handle invalid response format', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({ invalid: 'format' }),
      })

      try {
        await client.get('/api/state')
        expect.fail('Should have thrown ApiError')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        expect((error as ApiError).message).toContain('Invalid API response format')
      }
    })
  })

  describe('FormData requests', () => {
    it('should handle multipart file upload with Bearer token', async () => {
      client.setToken('officer-token')

      const formData = new FormData()
      formData.append('file', new Blob(['audio data'], { type: 'audio/ogg' }))

      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ok: true,
          data: { media_id: 'MD-000001' },
        }),
      })

      const result = await client.postForm('/api/merchants/S-0142/voice', formData)
      expect(result).toEqual({ media_id: 'MD-000001' })

      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            Authorization: 'Bearer officer-token',
          }),
        })
      )
    })
  })
})
