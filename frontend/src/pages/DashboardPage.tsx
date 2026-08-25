import { useState } from 'react'
import { ChatWindow } from '../components/ChatWindow'
import { DocumentList } from '../components/DocumentList'
import { DocumentUpload } from '../components/DocumentUpload'
import { useAuth } from '../hooks/authContext'

export function DashboardPage() {
  const { email, logout } = useAuth()
  const [documentsVersion, setDocumentsVersion] = useState(0)

  return (
    <div className="flex h-screen flex-col bg-neutral-50">
      <header className="flex items-center justify-between border-b border-neutral-200 bg-white px-6 py-3">
        <h1 className="text-lg font-semibold text-neutral-900">AI Knowledge Assistant</h1>
        <div className="flex items-center gap-3 text-sm text-neutral-500">
          {email && <span>{email}</span>}
          <button
            type="button"
            onClick={logout}
            className="rounded border border-neutral-300 px-3 py-1.5 hover:bg-neutral-100"
          >
            Log out
          </button>
        </div>
      </header>
      <div className="flex flex-1 gap-4 overflow-hidden p-4">
        <aside className="flex w-72 shrink-0 flex-col gap-3 overflow-y-auto">
          <DocumentUpload onUploaded={() => setDocumentsVersion((version) => version + 1)} />
          <DocumentList refreshToken={documentsVersion} />
        </aside>
        <main className="flex-1 overflow-hidden rounded-lg border border-neutral-200 bg-white p-4">
          <ChatWindow documentsVersion={documentsVersion} />
        </main>
      </div>
    </div>
  )
}
