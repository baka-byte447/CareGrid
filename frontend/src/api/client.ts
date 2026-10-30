/**
 * client.ts — CareGrid API HTTP client
 *
 * Single fetch wrapper: base URL from env, JSON, 15s timeout, typed ApiError.
 * Never hardcodes URLs. All components use hooks, not fetch directly.
 */

export interface ApiError {
  status: number
  message: string
  detail?: string
}

export class ApiRequestError extends Error {
  public readonly status: number
  public readonly detail: string | undefined

  constructor(error: ApiError) {
    super(error.message)
    this.name = 'ApiRequestError'
    this.status = error.status
    this.detail = error.detail
  }
}

const BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? '/api'
const TIMEOUT_MS = 15_000

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS)

  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...(init?.headers ?? {}),
      },
    })

    clearTimeout(timeoutId)

    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText })) as { detail?: string }
      throw new ApiRequestError({
        status: res.status,
        message: body.detail ?? `HTTP ${res.status}`,
        detail: body.detail,
      })
    }

    return res.json() as Promise<T>
  } catch (err) {
    clearTimeout(timeoutId)
    if (err instanceof ApiRequestError) throw err
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiRequestError({ status: 408, message: 'Request timed out after 15 seconds' })
    }
    throw new ApiRequestError({ status: 0, message: 'Network error — is the backend running?' })
  }
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path, { method: 'GET' })
}

export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}
