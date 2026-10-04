export type UserRole = 'admin' | 'analyst' | 'reviewer'

export interface User {
  id: string
  email: string
  full_name: string
  role: UserRole
}

export interface SessionResponse {
  user: User
  csrf_token: string
}
