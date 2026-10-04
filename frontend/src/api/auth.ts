import type { SessionResponse } from '../types/auth'
import { apiGet, apiPost } from './client'

export function login(email: string, password: string): Promise<SessionResponse> {
  return apiPost<SessionResponse>('/auth/login', { email, password })
}

export function logout(): Promise<void> {
  return apiPost<void>('/auth/logout')
}

export function fetchSession(): Promise<SessionResponse> {
  return apiGet<SessionResponse>('/auth/me')
}
