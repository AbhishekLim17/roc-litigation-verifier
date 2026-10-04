const API_BASE = '/api/v1'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  })
  // /health returns a JSON body with 503 when a dependency is down; surface it rather than throwing.
  if (!response.ok && response.status !== 503) {
    throw new ApiError(response.status, `Request failed: ${response.status}`)
  }
  return (await response.json()) as T
}
