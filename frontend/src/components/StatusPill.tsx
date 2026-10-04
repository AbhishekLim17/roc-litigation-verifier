type Tone = 'ok' | 'warn' | 'down' | 'pending'

const TONES: Record<Tone, string> = {
  ok: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  warn: 'bg-amber-50 text-amber-700 ring-amber-600/20',
  down: 'bg-rose-50 text-rose-700 ring-rose-600/20',
  pending: 'bg-slate-100 text-slate-600 ring-slate-500/20',
}

const DOTS: Record<Tone, string> = {
  ok: 'bg-emerald-500',
  warn: 'bg-amber-500',
  down: 'bg-rose-500',
  pending: 'bg-slate-400',
}

export function StatusPill({ tone, label }: { tone: Tone; label: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${TONES[tone]}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${DOTS[tone]}`} aria-hidden="true" />
      {label}
    </span>
  )
}
