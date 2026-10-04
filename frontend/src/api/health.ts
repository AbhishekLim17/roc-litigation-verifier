import type { HealthResponse } from '../types/health'

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch('/api/v1/health', { headers: { Accept: 'application/json' } })
  // /health returns a JSON body with 503 when a dependency is down; show it rather than failing.
  if (!response.ok && response.status !== 503) {
    throw new Error(`Health check failed (${response.status})`)
  }
  return (await response.json()) as HealthResponse
}
