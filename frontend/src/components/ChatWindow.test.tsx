import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ChatWindow } from './ChatWindow'
import * as conversationsApi from '../api/conversations'
import * as documentsApi from '../api/documents'
import * as streamApi from '../api/stream'
import { NOT_FOUND_MESSAGE } from '../constants'
import type { StreamHandlers } from '../api/stream'

vi.mock('../api/conversations')
vi.mock('../api/documents')
vi.mock('../api/stream')

const conversation = {
  id: 'conv-1',
  title: 'My conversation',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

beforeEach(() => {
  vi.mocked(conversationsApi.listConversations).mockResolvedValue({
    items: [conversation],
    total: 1,
    limit: 50,
    offset: 0,
  })
  vi.mocked(documentsApi.listDocuments).mockResolvedValue({
    items: [],
    total: 0,
    limit: 100,
    offset: 0,
  })
  vi.mocked(conversationsApi.listMessages).mockResolvedValue({ items: [], total: 0 })
  vi.mocked(streamApi.streamMessage).mockReset()
})

describe('ChatWindow', () => {
  it('loads a selected conversation and shows its citations', async () => {
    vi.mocked(conversationsApi.listMessages).mockResolvedValue({
      items: [
        { id: 'm1', role: 'user', content: 'What was Q3 revenue?', created_at: new Date().toISOString() },
        {
          id: 'm2',
          role: 'assistant',
          content: 'According to [source 1], Q3 revenue was $5M.',
          created_at: new Date().toISOString(),
          citations: [
            {
              document_id: 'doc-1',
              document_name: 'report.pdf',
              page_number: 4,
              chunk_id: 'chunk-1',
              similarity_score: 0.86,
              rank: 1,
            },
          ],
        },
      ],
      total: 2,
    })

    render(<ChatWindow documentsVersion={0} />)

    await userEvent.click(await screen.findByText('My conversation'))

    expect(await screen.findByText(/Q3 revenue was \$5M/)).toBeInTheDocument()
    expect(screen.getByTestId('citation-card')).toHaveTextContent('report.pdf')
  })

  it('renders the fixed refusal message in a distinct "not found" state', async () => {
    vi.mocked(streamApi.streamMessage).mockImplementation(
      async (_conversationId: string, _content: string, handlers: StreamHandlers) => {
        handlers.onToken?.(NOT_FOUND_MESSAGE)
        handlers.onCitations?.([])
      },
    )

    render(<ChatWindow documentsVersion={0} />)
    await userEvent.click(await screen.findByText('My conversation'))

    await userEvent.type(screen.getByLabelText('Question'), 'What is the CEO salary?')
    await userEvent.click(screen.getByRole('button', { name: 'Send' }))

    const streamedMessage = await screen.findByTestId('streaming-message')
    expect(streamedMessage).toHaveTextContent(NOT_FOUND_MESSAGE)
    expect(streamedMessage.className).toMatch(/amber/)
  })

  it('creates a new conversation scoped to the selected documents', async () => {
    vi.mocked(documentsApi.listDocuments).mockResolvedValue({
      items: [
        {
          id: 'doc-1',
          original_filename: 'report.pdf',
          status: 'completed',
          page_count: 3,
          created_at: new Date().toISOString(),
        },
      ],
      total: 1,
      limit: 100,
      offset: 0,
    })
    vi.mocked(conversationsApi.createConversation).mockResolvedValue({
      id: 'conv-2',
      title: null,
      document_ids: ['doc-1'],
      created_at: new Date().toISOString(),
    })

    render(<ChatWindow documentsVersion={0} />)

    await userEvent.click(await screen.findByRole('button', { name: 'New conversation' }))
    await userEvent.click(await screen.findByLabelText('Scope to report.pdf'))
    await userEvent.click(screen.getByRole('button', { name: 'Start' }))

    await waitFor(() =>
      expect(conversationsApi.createConversation).toHaveBeenCalledWith(['doc-1']),
    )
  })
})
