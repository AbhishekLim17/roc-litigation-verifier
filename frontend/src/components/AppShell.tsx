import type { ReactNode } from 'react'
import type { User } from '../types/auth'

const ROLE_LABELS: Record<User['role'], string> = {
  admin: 'Administrator',
  analyst: 'Analyst',
  reviewer: 'Reviewer',
}

export function AppShell({
  user,
  onSignOut,
  children,
}: {
  user: User
  onSignOut: () => void
  children: ReactNode
}) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-slate-900 text-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-slate-400">Internal</p>
            <h1 className="text-lg font-semibold">ROC Litigation Verification</h1>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className="text-sm font-medium">{user.full_name}</p>
              <p className="text-xs text-slate-400">{ROLE_LABELS[user.role]}</p>
            </div>
            <button
              type="button"
              onClick={onSignOut}
              className="rounded-md border border-slate-600 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-800"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        {children}
        <p className="mt-8 text-xs text-slate-500">
          This application is an automated verification aid and does not constitute legal advice or
          a legal determination of fraud.
        </p>
      </main>
    </div>
  )
}
