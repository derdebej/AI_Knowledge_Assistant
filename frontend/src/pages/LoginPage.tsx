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
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-4">
      <div className="pointer-events-none absolute -top-40 left-1/2 h-96 w-[36rem] -translate-x-1/2 rounded-full bg-violet-600/20 blur-3xl" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-72 w-72 rounded-full bg-blue-600/10 blur-3xl" />

      <div className="animate-fade-in-up relative w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 to-blue-500 shadow-lg shadow-violet-500/25">
            <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6 text-white">
              <path
                d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <h1 className="text-xl font-semibold tracking-tight text-white">AI Knowledge Assistant</h1>
          <p className="mt-1.5 text-sm text-slate-400">
            {mode === 'login' ? 'Welcome back — log in to continue' : 'Create your account to get started'}
          </p>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-7 shadow-2xl shadow-black/40 backdrop-blur-xl">
          <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
            {mode === 'register' && (
              <label className="flex flex-col gap-1.5 text-sm text-slate-300">
                Full name <span className="text-slate-500">(optional)</span>
                <input
                  className="rounded-lg border border-white/10 bg-white/[0.04] px-3.5 py-2.5 text-sm text-white placeholder-slate-500 outline-none transition-all focus:border-violet-400/50 focus:bg-white/[0.06] focus:ring-2 focus:ring-violet-500/20"
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                  placeholder="Jane Doe"
                />
              </label>
            )}
            <label className="flex flex-col gap-1.5 text-sm text-slate-300">
              Email
              <input
                type="email"
                required
                className="rounded-lg border border-white/10 bg-white/[0.04] px-3.5 py-2.5 text-sm text-white placeholder-slate-500 outline-none transition-all focus:border-violet-400/50 focus:bg-white/[0.06] focus:ring-2 focus:ring-violet-500/20"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
              />
            </label>
            <label className="flex flex-col gap-1.5 text-sm text-slate-300">
              Password
              <input
                type="password"
                required
                minLength={8}
                className="rounded-lg border border-white/10 bg-white/[0.04] px-3.5 py-2.5 text-sm text-white placeholder-slate-500 outline-none transition-all focus:border-violet-400/50 focus:bg-white/[0.06] focus:ring-2 focus:ring-violet-500/20"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="••••••••"
              />
            </label>
            {error && (
              <p role="alert" className="animate-fade-in rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-300">
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={submitting}
              className="group relative mt-2 flex items-center justify-center gap-2 overflow-hidden rounded-lg bg-gradient-to-r from-violet-600 to-blue-600 px-3 py-2.5 text-sm font-medium text-white shadow-lg shadow-violet-600/25 transition-all hover:shadow-violet-600/40 hover:brightness-110 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:brightness-100"
            >
              {submitting && (
                <svg className="h-4 w-4 animate-spin text-white/80" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                </svg>
              )}
              {submitting ? 'Please wait...' : mode === 'login' ? 'Log in' : 'Create account'}
            </button>
          </form>
        </div>

        <button
          type="button"
          className="mt-5 w-full text-center text-sm text-slate-400 transition-colors hover:text-slate-200"
          onClick={() => {
            setMode(mode === 'login' ? 'register' : 'login')
            setError(null)
          }}
        >
          {mode === 'login' ? (
            <>Don&rsquo;t have an account? <span className="font-medium text-violet-400">Register</span></>
          ) : (
            <>Already have an account? <span className="font-medium text-violet-400">Log in</span></>
          )}
        </button>
      </div>
    </main>
  )
}
