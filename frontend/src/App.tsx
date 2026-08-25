import { useAuth } from './hooks/authContext'
import { AuthProvider } from './hooks/useAuth'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'

function AppContent() {
  const { isAuthenticated } = useAuth()
  return isAuthenticated ? <DashboardPage /> : <LoginPage />
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}

export default App
