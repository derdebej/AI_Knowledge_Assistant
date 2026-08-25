import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { CitationCard } from './CitationCard'
import type { Citation } from '../types/api'

const citation: Citation = {
  document_id: 'doc-1',
  document_name: 'report.pdf',
  page_number: 4,
  chunk_id: 'chunk-1',
  similarity_score: 0.86,
  rank: 1,
}

describe('CitationCard', () => {
  it('renders document name, page number, rank and similarity score', () => {
    render(<CitationCard citation={citation} />)

    expect(screen.getByText(/report\.pdf/)).toBeInTheDocument()
    expect(screen.getByText(/p\. 4/)).toBeInTheDocument()
    expect(screen.getByText(/\[1\]/)).toBeInTheDocument()
    expect(screen.getByText('86% match')).toBeInTheDocument()
  })

  it('omits the page suffix when page_number is null', () => {
    render(<CitationCard citation={{ ...citation, page_number: null }} />)

    expect(screen.queryByText(/p\./)).not.toBeInTheDocument()
  })
})
