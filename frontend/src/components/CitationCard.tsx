import type { Citation } from '../types/api'

interface CitationCardProps {
  citation: Citation
}

// No snippet field exists on CitationResponse (specs/API.md §3 only sends
// document_id/name, page_number, chunk_id, similarity_score, rank) - the
// backend never returns chunk text over this endpoint, so there's nothing
// to render beyond what's shown here.
export function CitationCard({ citation }: CitationCardProps) {
  return (
    <div
      data-testid="citation-card"
      className="rounded border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-600"
    >
      <div className="flex items-center justify-between gap-3">
        <span className="font-medium text-neutral-800">
          [{citation.rank}] {citation.document_name}
          {citation.page_number != null ? ` - p. ${citation.page_number}` : ''}
        </span>
        <span className="whitespace-nowrap text-neutral-400">
          {Math.round(citation.similarity_score * 100)}% match
        </span>
      </div>
    </div>
  )
}
