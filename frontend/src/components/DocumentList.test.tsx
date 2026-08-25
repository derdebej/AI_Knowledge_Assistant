import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DocumentList } from './DocumentList'
import * as documentsApi from '../api/documents'
import type { DocumentListItem } from '../types/api'

vi.mock('../api/documents')

const baseDoc: DocumentListItem = {
  id: 'doc-1',
  original_filename: 'report.pdf',
  status: 'completed',
  page_count: 3,
  created_at: new Date().toISOString(),
}

describe('DocumentList', () => {
  beforeEach(() => {
    vi.mocked(documentsApi.listDocuments).mockReset()
    vi.mocked(documentsApi.getDocumentStatus).mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders a status badge per document', async () => {
    vi.mocked(documentsApi.listDocuments).mockResolvedValue({
      items: [baseDoc],
      total: 1,
      limit: 100,
      offset: 0,
    })

    render(<DocumentList refreshToken={0} />)

    expect(await screen.findByTestId('status-doc-1')).toHaveTextContent('completed')
    expect(screen.getByText('report.pdf')).toBeInTheDocument()
  })

  it('shows an empty state when there are no documents', async () => {
    vi.mocked(documentsApi.listDocuments).mockResolvedValue({
      items: [],
      total: 0,
      limit: 100,
      offset: 0,
    })

    render(<DocumentList refreshToken={0} />)

    expect(await screen.findByText('No documents uploaded yet.')).toBeInTheDocument()
  })

  it('polls the status endpoint while a document is processing', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.mocked(documentsApi.listDocuments).mockResolvedValue({
      items: [{ ...baseDoc, status: 'processing' }],
      total: 1,
      limit: 100,
      offset: 0,
    })
    vi.mocked(documentsApi.getDocumentStatus).mockResolvedValue({
      id: 'doc-1',
      status: 'completed',
      error_message: null,
    })

    render(<DocumentList refreshToken={0} />)
    await waitFor(() => expect(screen.getByTestId('status-doc-1')).toHaveTextContent('processing'))

    await vi.advanceTimersByTimeAsync(3000)

    await waitFor(() => expect(documentsApi.getDocumentStatus).toHaveBeenCalledWith('doc-1'))
    await waitFor(() => expect(screen.getByTestId('status-doc-1')).toHaveTextContent('completed'))
  })
})
