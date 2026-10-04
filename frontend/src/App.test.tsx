import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

function mockFetch(body: unknown, status = 200) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: status < 400, status, json: async () => body }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('App', () => {
  it('shows connected status when the API and database are healthy', async () => {
    mockFetch({
      status: 'ok',
      version: '0.1.0',
      environment: 'development',
      database: 'ok',
      roc_provider: 'mock',
    })
    render(<App />)
    expect(await screen.findByText('Connected')).toBeInTheDocument()
    expect(screen.getByText('Online')).toBeInTheDocument()
    expect(screen.getByText('Mock data')).toBeInTheDocument()
  })

  it('shows the database as unavailable when health is degraded', async () => {
    mockFetch(
      {
        status: 'degraded',
        version: '0.1.0',
        environment: 'development',
        database: 'unavailable',
        roc_provider: 'mock',
      },
      503,
    )
    render(<App />)
    expect(await screen.findByText('Unavailable')).toBeInTheDocument()
  })

  it('shows the API as unreachable when the request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network')))
    render(<App />)
    expect(await screen.findByText('Unreachable')).toBeInTheDocument()
  })

  it('always shows the legal disclaimer', () => {
    mockFetch({})
    render(<App />)
    expect(screen.getByText(/does not constitute legal advice/)).toBeInTheDocument()
  })
})
