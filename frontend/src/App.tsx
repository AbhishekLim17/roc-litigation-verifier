import { useAuth } from './auth/AuthContext'
import { AppShell } from './components/AppShell'
import { HomePage } from './pages/HomePage'
import { LoginPage } from './pages/LoginPage'

function App() {
  const { state, signOut } = useAuth()

  if (state.status === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-slate-500">
        Loading…
      </div>
    )
  }
  if (state.status === 'signed-out') {
    return <LoginPage />
  }
  return (
    <AppShell user={state.user} onSignOut={() => void signOut()}>
      <HomePage />
    </AppShell>
  )
}

export default App
