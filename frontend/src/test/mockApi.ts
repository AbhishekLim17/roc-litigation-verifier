import { vi } from 'vitest'

type Handler = (init: RequestInit | undefined) => { status: number; body?: unknown }

/** Stub global fetch with a map of "METHOD /path" -> handler. Returns the mock for assertions. */
export function mockApi(routes: Record<string, Handler>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${String(input)}`
    const handler = routes[key]
    if (!handler) throw new Error(`Unexpected request: ${key}`)
    const { status, body } = handler(init)
    return {
      ok: status < 400,
      status,
      json: async () => body,
    } as Response
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

export const HEALTHY = {
  status: 200,
  body: { status: 'ok', version: '0.1.0', environment: 'development', database: 'ok', roc_provider: 'mock' },
}

export const SESSION = {
  user: { id: 'u1', email: 'analyst@example.com', full_name: 'Asha Analyst', role: 'analyst' },
  csrf_token: 'csrf-abc',
}
