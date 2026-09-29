/**
 * API Client - fetch wrapper with envelope handling
 * Handles the {ok, data|error} envelope format (SPEC §19.2)
 */

import type { Envelope, ErrorEnvelope } from './types'

type RequestMethod = 'GET' | 'POST' | 'PUT' | 'DELETE'

interface RequestOptions {
  method?: RequestMethod
  headers?: Record<string, string>
  body?: unknown
  signal?: AbortSignal
}

class ApiClient {
  private baseUrl: string
  private token: string | null = null

  constructor(baseUrl: string = import.meta.env.VITE_API_BASE || '') {
    this.baseUrl = baseUrl
  }

  setToken(token: string): void {
    this.token = token
  }

  private async request<T>(
    path: string,
    options: RequestOptions = {}
  ): Promise<Envelope<T>> {
    const url = `${this.baseUrl}${path}`
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...options.headers,
    }

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`
    }

    const response = await fetch(url, {
      method: options.method || 'GET',
      headers,
      body:
        options.body && options.method !== 'GET'
          ? JSON.stringify(options.body)
          : undefined,
      signal: options.signal,
    })

    const data = await response.json()

    if (!response.ok) {
      const errorData = data as ErrorEnvelope
      throw new ApiError(
        errorData.error?.message || `HTTP ${response.status}`,
        response.status,
        errorData.error?.code,
        errorData.error?.fields
      )
    }

    if (!('ok' in data)) {
      throw new ApiError('Invalid API response format', 0)
    }

    if (!data.ok) {
      const errorData = data as ErrorEnvelope
      throw new ApiError(
        errorData.error?.message || 'API error',
        0,
        errorData.error?.code,
        errorData.error?.fields
      )
    }

    return data as Envelope<T>
  }

  async get<T>(path: string, signal?: AbortSignal): Promise<T> {
    const response = await this.request<T>(path, { method: 'GET', signal })
    return response.data
  }

  async post<T>(
    path: string,
    body: unknown,
    signal?: AbortSignal
  ): Promise<T> {
    const response = await this.request<T>(path, {
      method: 'POST',
      body,
      signal,
    })
    return response.data
  }

  async postForm<T>(
    path: string,
    formData: FormData,
    signal?: AbortSignal
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`
    const headers: Record<string, string> = {}

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`
    }

    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: formData,
      signal,
    })

    const data = await response.json()

    if (!response.ok) {
      const errorData = data as ErrorEnvelope
      throw new ApiError(
        errorData.error?.message || `HTTP ${response.status}`,
        response.status,
        errorData.error?.code,
        errorData.error?.fields
      )
    }

    if (!data.ok) {
      const errorData = data as ErrorEnvelope
      throw new ApiError(
        errorData.error?.message || 'API error',
        0,
        errorData.error?.code,
        errorData.error?.fields
      )
    }

    return (data as Envelope<T>).data
  }

  async put<T>(
    path: string,
    body: unknown,
    signal?: AbortSignal
  ): Promise<T> {
    const response = await this.request<T>(path, {
      method: 'PUT',
      body,
      signal,
    })
    return response.data
  }
}

export class ApiError extends Error {
  public statusCode: number
  public code: string
  public fields?: Record<string, string>

  constructor(
    message: string,
    statusCode: number = 0,
    code: string = 'UNKNOWN',
    fields?: Record<string, string>
  ) {
    super(message)
    this.name = 'ApiError'
    this.statusCode = statusCode
    this.code = code
    this.fields = fields
  }
}

// Export singleton instance
const apiClient = new ApiClient()
export { apiClient, ApiClient }
