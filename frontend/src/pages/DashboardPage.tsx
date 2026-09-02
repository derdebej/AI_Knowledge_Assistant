import { useState } from 'react'
import { ChatWindow } from '../components/ChatWindow'
import { DocumentList } from '../components/DocumentList'
import { DocumentUpload } from '../components/DocumentUpload'
import { useAuth } from '../hooks/authContext'

export function DashboardPage() {
  const { email, logout } = useAuth()
  const [documentsVersion, setDocumentsVersion] = useState(0)

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <header className="flex shrink-0 items-center justify-between border-b border-white/10 bg-white/[0.02] px-6 py-3.5 backdrop-blur-xl">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-blue-500 shadow-md shadow-violet-500/20">
            <svg viewBox="0 0 24 24" fill="none" className="h-4.5 w-4.5 text-white">
              <path
                d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <h1 className="text-[15px] font-semibold tracking-tight text-white">AI Knowledge Assistant</h1>
        </div>
        <div className="flex items-center gap-3">
          {email && (
            <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] py-1 pl-1 pr-3 text-sm text-slate-300">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-violet-500/30 to-blue-500/30 text-[11px] font-medium text-violet-200">
                {email[0]?.toUpperCase()}
              </span>
              <span className="max-w-[14rem] truncate">{email}</span>
            </div>
          )}
          <button
            type="button"
            onClick={logout}
            className="rounded-lg border border-white/10 bg-white/[0.03] px-3.5 py-1.5 text-sm text-slate-300 transition-all hover:border-white/20 hover:bg-white/[0.07] hover:text-white"
          >
            Log out
          </button>
        </div>
      </header>
      <div className="flex flex-1 gap-4 overflow-hidden p-4">
        <aside className="flex w-80 shrink-0 flex-col gap-4 overflow-y-auto">
          <DocumentUpload onUploaded={() => setDocumentsVersion((version) => version + 1)} />
          <DocumentList refreshToken={documentsVersion} />
        </aside>
        <main className="flex-1 overflow-hidden rounded-2xl border border-white/10 bg-white/[0.02] shadow-2xl shadow-black/20 backdrop-blur-xl">
          <ChatWindow documentsVersion={documentsVersion} />
        </main>
      </div>
    </div>
  )
}
