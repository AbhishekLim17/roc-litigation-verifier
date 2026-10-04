import { useEffect, useState } from 'react'
import { fetchHealth } from '../api/health'
import type { HealthResponse } from '../types/health'
import { StatusPill } from './StatusPill'

type State =
  | { kind: 'loading' }
  | { kind: 'loaded'; health: HealthResponse }
  | { kind: 'error' }

export function SystemStatus() {
  const [state, setState] = useState<State>({ kind: 'loading' })

  useEffect(() => {
    let cancelled = false
    fetchHealth()
      .then((health) => !cancelled && setState({ kind: 'loaded', health }))
      .catch(() => !cancelled && setState({ kind: 'error' }))
    return () => {
      cancelled = true
    }
  }, [])

  const rows: { name: string; pill: React.ReactNode }[] = [
    {
      name: 'API server',
      pill:
        state.kind === 'loading' ? (
          <StatusPill tone="pending" label="Checking" />
        ) : state.kind === 'error' ? (
          <StatusPill tone="down" label="Unreachable" />
        ) : (
          <StatusPill tone="ok" label="Online" />
        ),
    },
    {
      name: 'Database',
      pill:
        state.kind !== 'loaded' ? (
          <StatusPill tone="pending" label="Unknown" />
        ) : state.health.database === 'ok' ? (
          <StatusPill tone="ok" label="Connected" />
        ) : (
          <StatusPill tone="down" label="Unavailable" />
        ),
    },
    {
      name: 'ROC data provider',
      pill:
        state.kind !== 'loaded' ? (
          <StatusPill tone="pending" label="Unknown" />
        ) : (
          <StatusPill
            tone={state.health.roc_provider === 'mock' ? 'warn' : 'ok'}
            label={state.health.roc_provider === 'mock' ? 'Mock data' : state.health.roc_provider}
          />
        ),
    },
  ]

  return (
    <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <header className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
        <h2 className="text-sm font-semibold text-slate-900">System status</h2>
        {state.kind === 'loaded' && (
          <span className="text-xs text-slate-500">
            v{state.health.version} · {state.health.environment}
          </span>
        )}
      </header>
      <ul className="divide-y divide-slate-100">
        {rows.map((row) => (
          <li key={row.name} className="flex items-center justify-between px-5 py-3 text-sm">
            <span className="text-slate-700">{row.name}</span>
            {row.pill}
          </li>
        ))}
      </ul>
    </section>
  )
}
