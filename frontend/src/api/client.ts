// Base fetch wrapper: attaches the bearer token, unwraps the
// { detail, error_code } error shape from specs/API.md §5.

export const API_BASE = '/api/v1'

const TOKEN_KEY = 'aika_token'

export class ApiError extends Error {
  status: number
  errorCode?: string

  constructor(message: string, status: number, errorCode?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.errorCode = errorCode
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

function authHeaders(): HeadersInit {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function parseErrorBody(response: Response): Promise<{ detail: string; error_code?: string }> {
  try {
    const body = await response.json()
    return {
      detail: typeof body?.detail === 'string' ? body.detail : response.statusText,
      error_code: typeof body?.error_code === 'string' ? body.error_code : undefined,
    }
  } catch {
    return { detail: response.statusText }
  }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isFormData = init.body instanceof FormData
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init.body && !isFormData ? { 'Content-Type': 'application/json' } : {}),
      ...authHeaders(),
      ...init.headers,
    },
  })

  if (response.status === 204) {
    return undefined as T
  }

  if (!response.ok) {
    const { detail, error_code: errorCode } = await parseErrorBody(response)
    throw new ApiError(detail, response.status, errorCode)
  }

  return (await response.json()) as T
}
