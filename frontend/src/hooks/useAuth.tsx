import { useCallback, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { login as loginRequest, register as registerRequest } from '../api/auth'
import { clearToken, getToken, setToken } from '../api/client'
import { AuthContext } from './authContext'

// Login/register only return an access token (no user profile endpoint
// exists), so the email is remembered client-side purely for display.
const EMAIL_KEY = 'aika_email'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() => getToken())
  const [email, setEmail] = useState<string | null>(() => localStorage.getItem(EMAIL_KEY))

  const login = useCallback(async (loginEmail: string, password: string) => {
    const response = await loginRequest(loginEmail, password)
    setToken(response.access_token)
    localStorage.setItem(EMAIL_KEY, loginEmail)
    setTokenState(response.access_token)
    setEmail(loginEmail)
  }, [])

  const register = useCallback(
    async (registerEmail: string, password: string, fullName?: string) => {
      await registerRequest(registerEmail, password, fullName)
      await login(registerEmail, password)
    },
    [login],
  )

  const logout = useCallback(() => {
    clearToken()
    localStorage.removeItem(EMAIL_KEY)
    setTokenState(null)
    setEmail(null)
  }, [])

  const value = useMemo(
    () => ({ isAuthenticated: token !== null, email, login, register, logout }),
    [token, email, login, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
