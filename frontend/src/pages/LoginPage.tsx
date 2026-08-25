import { useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError } from '../api/client'
import { useAuth } from '../hooks/authContext'

type Mode = 'login' | 'register'

export function LoginPage() {
  const { login, register } = useAuth()
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      if (mode === 'login') {
        await login(email, password)
      } else {
        await register(email, password, fullName || undefined)
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-neutral-50">
      <div className="w-full max-w-sm rounded-lg border border-neutral-200 bg-white p-8 shadow-sm">
        <h1 className="mb-1 text-xl font-semibold text-neutral-900">AI Knowledge Assistant</h1>
        <p className="mb-6 text-sm text-neutral-500">
          {mode === 'login' ? 'Log in to your account' : 'Create a new account'}
        </p>
        <form className="flex flex-col gap-3" onSubmit={handleSubmit}>
          {mode === 'register' && (
            <label className="flex flex-col gap-1 text-sm text-neutral-700">
              Full name (optional)
              <input
                className="rounded border border-neutral-300 px-3 py-2 text-sm"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
              />
            </label>
          )}
          <label className="flex flex-col gap-1 text-sm text-neutral-700">
            Email
            <input
              type="email"
              required
              className="rounded border border-neutral-300 px-3 py-2 text-sm"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-neutral-700">
            Password
            <input
              type="password"
              required
              minLength={8}
              className="rounded border border-neutral-300 px-3 py-2 text-sm"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          {error && (
            <p role="alert" className="text-sm text-red-600">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={submitting}
            className="mt-2 rounded bg-neutral-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {submitting ? 'Please wait...' : mode === 'login' ? 'Log in' : 'Register'}
          </button>
        </form>
        <button
          type="button"
          className="mt-4 text-sm text-neutral-500 underline"
          onClick={() => {
            setMode(mode === 'login' ? 'register' : 'login')
            setError(null)
          }}
        >
          {mode === 'login' ? "Don't have an account? Register" : 'Already have an account? Log in'}
        </button>
      </div>
    </main>
  )
}
