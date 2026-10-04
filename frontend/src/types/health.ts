export type ComponentStatus = 'ok' | 'unavailable'

export interface HealthResponse {
  status: 'ok' | 'degraded'
  version: string
  environment: string
  database: ComponentStatus
  roc_provider: string
}
