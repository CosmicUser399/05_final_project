export interface HealthResponse {
  status: string
  version: string
}

export interface ReadyResponse {
  status: string
  checks: Record<string, boolean>
}
