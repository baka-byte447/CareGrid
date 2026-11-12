
/**
 * client.ts — CareGrid API HTTP client
 *
 * Centralized fetch wrapper:
 * - Base URL from environment
 * - JSON requests and responses
 * - 15-second timeout
 * - JWT Bearer token authentication
 * - Typed API errors
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
const TOKEN_KEY = 'caregrid_access_token'

// ─── JWT Token Management ────────────────────────────────────────────────────

export function setAccessToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token)
}

export function getAccessToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY)
}

export function clearAccessToken(): void {
  sessionStorage.removeItem(TOKEN_KEY)
}

// ─── HTTP Request Wrapper ────────────────────────────────────────────────────

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS)

  try {
    const headers = new Headers(init?.headers)

    if (!headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }

    // Automatically attach JWT to protected API requests.
    const token = getAccessToken()

    if (token && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`)
    }

    const res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers,
    })

    clearTimeout(timeoutId)

    if (!res.ok) {
      const body = await res.json().catch(
        () => ({ detail: res.statusText }),
      ) as { detail?: string }

      // An expired or invalid token requires re-authentication.
      if (res.status === 401) {
        clearAccessToken()
      }

      throw new ApiRequestError({
        status: res.status,
        message: body.detail ?? `HTTP ${res.status}`,
        detail: body.detail,
      })
    }

    return res.json() as Promise<T>
  } catch (err) {
    clearTimeout(timeoutId)

    if (err instanceof ApiRequestError) {
      throw err
    }

    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiRequestError({
        status: 408,
        message: 'Request timed out after 15 seconds',
      })
    }

    throw new ApiRequestError({
      status: 0,
      message: 'Network error — is the backend running?',
    })
  }
}

// ─── Public API Methods ─────────────────────────────────────────────────────

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path, { method: 'GET' })
}

export function apiPost<T>(
  path: string,
  body: unknown,
): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}
