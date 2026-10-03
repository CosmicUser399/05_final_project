/** Minimal typed HTTP client; replaced by an OpenAPI-generated one in P7. */

export interface ApiErrorBody {
  error: {
    code: string
    message: string
    entity: string | null
    entity_id: string | null
  }
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

const API_BASE = '/api/v1'

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  return (
    typeof value === 'object' &&
    value !== null &&
    'error' in value &&
    typeof (value as ApiErrorBody).error?.code === 'string'
  )
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: 'application/json' },
  })
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    if (isApiErrorBody(body)) {
      throw new ApiError(response.status, body.error.code, body.error.message)
    }
    throw new ApiError(response.status, 'UNKNOWN', response.statusText)
  }
  return body as T
}
