import { SystemStatus } from '../components/SystemStatus'

export function HomePage() {
  return (
    <div className="grid gap-6 md:grid-cols-3">
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm md:col-span-2">
        <h2 className="text-base font-semibold text-slate-900">Welcome</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          This workspace extracts company claims from litigation documents, checks them against
          official ROC records, and highlights inconsistencies for review. Case upload and
          verification will appear here as they are built.
        </p>
      </div>
      <SystemStatus />
    </div>
  )
}
