import { useEffect, useState } from 'react'

type HealthStatus = 'checking' | 'ok' | 'unreachable'

function App() {
  const [status, setStatus] = useState<HealthStatus>('checking')

  useEffect(() => {
    fetch('/api/v1/health')
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then(() => setStatus('ok'))
      .catch(() => setStatus('unreachable'))
  }, [])

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-neutral-50 text-neutral-900">
      <h1 className="text-2xl font-semibold">AI Knowledge Assistant</h1>
      <p className="text-neutral-500">
        Phase 1 scaffold - upload, chat, and citation UI land in Phase 7.
      </p>
      <p className="text-sm">
        Backend health:{' '}
        <span
          className={
            status === 'ok'
              ? 'font-medium text-green-600'
              : status === 'unreachable'
                ? 'font-medium text-red-600'
                : 'text-neutral-400'
          }
        >
          {status}
        </span>
      </p>
    </main>
  )
}

export default App
