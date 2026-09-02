import type { Citation } from '../types/api'

interface CitationCardProps {
  citation: Citation
}

// No snippet field exists on CitationResponse (specs/API.md §3 only sends
// document_id/name, page_number, chunk_id, similarity_score, rank) - the
// backend never returns chunk text over this endpoint, so there's nothing
// to render beyond what's shown here.
export function CitationCard({ citation }: CitationCardProps) {
  const matchPercent = Math.round(citation.similarity_score * 100)

  return (
    <div
      data-testid="citation-card"
      className="group flex items-center gap-2.5 rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2 text-xs transition-colors hover:border-violet-400/25 hover:bg-white/[0.05]"
    >
      <svg viewBox="0 0 24 24" fill="none" className="h-3.5 w-3.5 shrink-0 text-violet-400">
        <path
          d="M7 3h7l5 5v13a1 1 0 01-1 1H7a1 1 0 01-1-1V4a1 1 0 011-1zM14 3v5h5"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span className="min-w-0 flex-1 truncate font-medium text-slate-300">
        [{citation.rank}] {citation.document_name}
        {citation.page_number != null ? ` - p. ${citation.page_number}` : ''}
      </span>
      <span className="flex shrink-0 items-center gap-1.5 whitespace-nowrap text-slate-500">
        <span className="h-1 w-8 overflow-hidden rounded-full bg-white/10">
          <span
            className="block h-full rounded-full bg-gradient-to-r from-violet-500 to-blue-400"
            style={{ width: `${matchPercent}%` }}
          />
        </span>
        {matchPercent}% match
      </span>
    </div>
  )
}
