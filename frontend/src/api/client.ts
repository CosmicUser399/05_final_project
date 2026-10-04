/**
 * Typed HTTP client for `/api/v1`.
 *
 * Regenerated shapes live in `types.ts`. To refresh from OpenAPI run:
 * `npm run generate:api` (see `scripts/generate-api.mjs`).
 */

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

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as T
  }
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    if (isApiErrorBody(body)) {
      throw new ApiError(response.status, body.error.code, body.error.message)
    }
    throw new ApiError(response.status, 'UNKNOWN', response.statusText)
  }
  return body as T
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: 'application/json' },
  })
  return parseResponse<T>(response)
}

export async function apiSend<T>(
  method: 'POST' | 'PATCH' | 'PUT' | 'DELETE',
  path: string,
  body?: unknown,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      Accept: 'application/json',
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  return parseResponse<T>(response)
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return apiSend<T>('POST', path, body)
}

export async function apiPostWithHeaders<T>(
  path: string,
  body?: unknown,
  headers?: Record<string, string>,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...headers,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  return parseResponse<T>(response)
}

export async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  return apiSend<T>('PATCH', path, body)
}

export async function apiDelete(path: string): Promise<void> {
  await apiSend<void>('DELETE', path)
}
