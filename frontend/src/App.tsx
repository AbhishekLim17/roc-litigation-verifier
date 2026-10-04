import { SystemStatus } from './components/SystemStatus'

function App() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-slate-900 text-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-slate-400">Internal</p>
            <h1 className="text-lg font-semibold">ROC Litigation Verification</h1>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">
        <div className="grid gap-6 md:grid-cols-3">
          <div className="md:col-span-2 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-base font-semibold text-slate-900">Welcome</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              This workspace extracts company claims from litigation documents, checks them against
              official ROC records, and highlights inconsistencies for review. Case upload and
              verification will appear here as they are built.
            </p>
          </div>
          <SystemStatus />
        </div>

        <p className="mt-8 text-xs text-slate-500">
          This application is an automated verification aid and does not constitute legal advice or
          a legal determination of fraud.
        </p>
      </main>
    </div>
  )
}

export default App
