import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import * as authApi from '../api/auth'
import { setCsrfToken } from '../api/client'
import { AuthContext, type AuthState } from './AuthContext'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false
    authApi
      .fetchSession()
      .then((session) => {
        if (cancelled) return
        setCsrfToken(session.csrf_token)
        setState({ status: 'signed-in', user: session.user })
      })
      .catch(() => {
        if (!cancelled) setState({ status: 'signed-out' })
      })
    return () => {
      cancelled = true
    }
  }, [])

  const signIn = useCallback(async (email: string, password: string) => {
    const session = await authApi.login(email, password)
    setCsrfToken(session.csrf_token)
    setState({ status: 'signed-in', user: session.user })
  }, [])

  const signOut = useCallback(async () => {
    try {
      await authApi.logout()
    } finally {
      setCsrfToken(null)
      setState({ status: 'signed-out' })
    }
  }, [])

  const value = useMemo(() => ({ state, signIn, signOut }), [state, signIn, signOut])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
