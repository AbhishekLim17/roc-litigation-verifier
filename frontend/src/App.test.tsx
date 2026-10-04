import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { AuthProvider } from './auth/AuthProvider'
import { HEALTHY, SESSION, mockApi } from './test/mockApi'

function renderApp() {
  return render(
    <AuthProvider>
      <App />
    </AuthProvider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('authentication', () => {
  it('shows the login page when there is no session', async () => {
    mockApi({ 'GET /api/v1/auth/me': () => ({ status: 401, body: { detail: 'Not signed in' } }) })
    renderApp()
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('signs in and shows the workspace', async () => {
    const fetchMock = mockApi({
      'GET /api/v1/auth/me': () => ({ status: 401 }),
      'POST /api/v1/auth/login': () => ({ status: 200, body: SESSION }),
      'GET /api/v1/health': () => HEALTHY,
    })
    renderApp()
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText('Email'), 'analyst@example.com')
    await user.type(screen.getByLabelText('Password'), 'Correct-Horse-42')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText('Asha Analyst')).toBeInTheDocument()
    expect(await screen.findByText('Connected')).toBeInTheDocument()
    const loginCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/auth/login'))
    expect(JSON.parse(String(loginCall?.[1]?.body))).toEqual({
      email: 'analyst@example.com',
      password: 'Correct-Horse-42',
    })
  })

  it('shows an error and clears the password on bad credentials', async () => {
    mockApi({
      'GET /api/v1/auth/me': () => ({ status: 401 }),
      'POST /api/v1/auth/login': () => ({ status: 401, body: { detail: 'Invalid email or password' } }),
    })
    renderApp()
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText('Email'), 'analyst@example.com')
    await user.type(screen.getByLabelText('Password'), 'wrong')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password.')
    expect(screen.getByLabelText('Password')).toHaveValue('')
  })

  it('sends the CSRF token when signing out', async () => {
    const fetchMock = mockApi({
      'GET /api/v1/auth/me': () => ({ status: 200, body: SESSION }),
      'GET /api/v1/health': () => HEALTHY,
      'POST /api/v1/auth/logout': () => ({ status: 204 }),
    })
    renderApp()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Sign out' }))

    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument()
    const logoutCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/auth/logout'))
    const headers = (logoutCall?.[1]?.headers ?? {}) as Record<string, string>
    expect(headers['X-CSRF-Token']).toBe('csrf-abc')
  })
})

describe('system status', () => {
  it('shows the database as unavailable when health is degraded', async () => {
    mockApi({
      'GET /api/v1/auth/me': () => ({ status: 200, body: SESSION }),
      'GET /api/v1/health': () => ({ status: 503, body: { ...HEALTHY.body, status: 'degraded', database: 'unavailable' } }),
    })
    renderApp()
    expect(await screen.findByText('Unavailable')).toBeInTheDocument()
  })

  it('always shows the legal disclaimer inside the workspace', async () => {
    mockApi({
      'GET /api/v1/auth/me': () => ({ status: 200, body: SESSION }),
      'GET /api/v1/health': () => HEALTHY,
    })
    renderApp()
    expect(await screen.findByText(/does not constitute legal advice/)).toBeInTheDocument()
  })
})
