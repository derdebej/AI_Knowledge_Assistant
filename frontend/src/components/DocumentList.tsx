import { useEffect, useState } from 'react'
import { deleteDocument, getDocumentStatus, listDocuments } from '../api/documents'
import type { DocumentListItem } from '../types/api'

const POLL_INTERVAL_MS = 3000
const ACTIVE_STATUSES = new Set(['pending', 'processing'])

const STATUS_STYLES: Record<string, string> = {
  pending: 'bg-slate-500/15 text-slate-300',
  processing: 'bg-amber-500/15 text-amber-300',
  completed: 'bg-emerald-500/15 text-emerald-300',
  failed: 'bg-red-500/15 text-red-300',
}

const STATUS_DOT: Record<string, string> = {
  pending: 'bg-slate-400',
  processing: 'bg-amber-400 animate-pulse-glow',
  completed: 'bg-emerald-400',
  failed: 'bg-red-400',
}

const FILE_ICON_COLOR = 'text-slate-500'

interface DocumentListProps {
  refreshToken: number
  selectable?: boolean
  selectedIds?: string[]
  onToggleSelect?: (id: string) => void
}

export function DocumentList({
  refreshToken,
  selectable = false,
  selectedIds = [],
  onToggleSelect,
}: DocumentListProps) {
  const [documents, setDocuments] = useState<DocumentListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const response = await listDocuments({ limit: 100 })
        if (cancelled) return
        setDocuments(response.items)
        setError(null)
      } catch {
        if (!cancelled) setError('Could not load documents.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [refreshToken])

  // Polls every still-processing document on a single shared interval while
  // any are in flight (specs/API.md §2's lightweight status endpoint exists
  // exactly for this).
  useEffect(() => {
    if (!documents.some((doc) => ACTIVE_STATUSES.has(doc.status))) return undefined

    const interval = setInterval(async () => {
      const pending = documents.filter((doc) => ACTIVE_STATUSES.has(doc.status))
      const updates = await Promise.all(
        pending.map((doc) => getDocumentStatus(doc.id).catch(() => null)),
      )
      setDocuments((prev) =>
        prev.map((doc) => {
          const update = updates.find((candidate) => candidate?.id === doc.id)
          return update ? { ...doc, status: update.status } : doc
        }),
      )
    }, POLL_INTERVAL_MS)

    return () => clearInterval(interval)
  }, [documents])

  async function handleDelete(id: string) {
    setDocuments((prev) => prev.filter((doc) => doc.id !== id))
    await deleteDocument(id)
  }

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Documents</h2>
        {documents.length > 0 && (
          <span className="rounded-full bg-white/5 px-2 py-0.5 text-xs text-slate-400">{documents.length}</span>
        )}
      </div>

      {loading && (
        <ul className="flex flex-col gap-2">
          {[0, 1, 2].map((i) => (
            <li key={i} className="h-11 animate-pulse rounded-xl bg-white/[0.03]" />
          ))}
        </ul>
      )}

      {!loading && error && <p className="text-sm text-red-400">{error}</p>}

      {!loading && !error && documents.length === 0 && (
        <p className="text-sm text-slate-500">No documents uploaded yet.</p>
      )}

      {!loading && !error && documents.length > 0 && (
        <ul className="flex flex-col gap-1.5">
          {documents.map((doc) => (
            <li
              key={doc.id}
              className="group flex animate-fade-in-up items-center justify-between gap-2 rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2.5 text-sm transition-all hover:border-white/10 hover:bg-white/[0.05]"
            >
              <div className="flex min-w-0 items-center gap-2.5">
                {selectable && (
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(doc.id)}
                    onChange={() => onToggleSelect?.(doc.id)}
                    aria-label={`Select ${doc.original_filename}`}
                    className="h-3.5 w-3.5 shrink-0 accent-violet-500"
                  />
                )}
                <svg viewBox="0 0 24 24" fill="none" className={`h-4 w-4 shrink-0 ${FILE_ICON_COLOR}`}>
                  <path
                    d="M7 3h7l5 5v13a1 1 0 01-1 1H7a1 1 0 01-1-1V4a1 1 0 011-1zM14 3v5h5"
                    stroke="currentColor"
                    strokeWidth="1.6"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                <span className="truncate text-slate-200" title={doc.original_filename}>
                  {doc.original_filename}
                </span>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <span
                  data-testid={`status-${doc.id}`}
                  className={`flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS_STYLES[doc.status] ?? ''}`}
                >
                  <span className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[doc.status] ?? 'bg-slate-400'}`} />
                  {doc.status}
                </span>
                <button
                  type="button"
                  onClick={() => void handleDelete(doc.id)}
                  className="opacity-0 transition-opacity hover:text-red-400 group-hover:opacity-100"
                  aria-label={`Delete ${doc.original_filename}`}
                >
                  <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4 text-slate-500 hover:text-red-400">
                    <path
                      d="M3 6h18M8 6V4a1 1 0 011-1h6a1 1 0 011 1v2m3 0v14a1 1 0 01-1 1H6a1 1 0 01-1-1V6h14z"
                      stroke="currentColor"
                      strokeWidth="1.6"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
