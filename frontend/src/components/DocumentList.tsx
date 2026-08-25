import { useEffect, useState } from 'react'
import { deleteDocument, getDocumentStatus, listDocuments } from '../api/documents'
import type { DocumentListItem } from '../types/api'

const POLL_INTERVAL_MS = 3000
const ACTIVE_STATUSES = new Set(['pending', 'processing'])

const STATUS_STYLES: Record<string, string> = {
  pending: 'bg-neutral-200 text-neutral-700',
  processing: 'bg-amber-100 text-amber-700',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
}

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
    await deleteDocument(id)
    setDocuments((prev) => prev.filter((doc) => doc.id !== id))
  }

  if (loading) return <p className="text-sm text-neutral-400">Loading documents...</p>
  if (error) return <p className="text-sm text-red-600">{error}</p>
  if (documents.length === 0) {
    return <p className="text-sm text-neutral-400">No documents uploaded yet.</p>
  }

  return (
    <ul className="flex flex-col gap-2">
      {documents.map((doc) => (
        <li
          key={doc.id}
          className="flex items-center justify-between gap-2 rounded border border-neutral-200 px-3 py-2 text-sm"
        >
          <div className="flex items-center gap-2 overflow-hidden">
            {selectable && (
              <input
                type="checkbox"
                checked={selectedIds.includes(doc.id)}
                onChange={() => onToggleSelect?.(doc.id)}
                aria-label={`Select ${doc.original_filename}`}
              />
            )}
            <span className="truncate" title={doc.original_filename}>
              {doc.original_filename}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span
              data-testid={`status-${doc.id}`}
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[doc.status] ?? ''}`}
            >
              {doc.status}
            </span>
            <button
              type="button"
              onClick={() => void handleDelete(doc.id)}
              className="text-xs text-neutral-400 hover:text-red-600"
              aria-label={`Delete ${doc.original_filename}`}
            >
              Delete
            </button>
          </div>
        </li>
      ))}
    </ul>
  )
}
