import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useStreamingAnswer } from './useStreamingAnswer'
import * as streamApi from '../api/stream'
import { NOT_FOUND_MESSAGE } from '../constants'
import type { StreamHandlers } from '../api/stream'

vi.mock('../api/stream')

describe('useStreamingAnswer', () => {
  beforeEach(() => {
    vi.mocked(streamApi.streamMessage).mockReset()
  })

  it('accumulates tokens and citations, then transitions to done', async () => {
    vi.mocked(streamApi.streamMessage).mockImplementation(
      async (_conversationId: string, _content: string, handlers: StreamHandlers) => {
        handlers.onToken?.('Q3 revenue ')
        handlers.onToken?.('was $5M.')
        handlers.onCitations?.([
          {
            document_id: 'doc-1',
            document_name: 'report.pdf',
            page_number: 4,
            chunk_id: 'chunk-1',
            similarity_score: 0.86,
            rank: 1,
          },
        ])
        handlers.onDone?.('message-1')
      },
    )

    const { result } = renderHook(() => useStreamingAnswer())

    await act(async () => {
      await result.current.send('conversation-1', 'What was Q3 revenue?')
    })

    await waitFor(() => expect(result.current.status).toBe('done'))
    expect(result.current.content).toBe('Q3 revenue was $5M.')
    expect(result.current.citations).toHaveLength(1)
    expect(result.current.messageId).toBe('message-1')
    expect(result.current.isNotFound).toBe(false)
  })

  it('flags the fixed refusal message as not-found', async () => {
    vi.mocked(streamApi.streamMessage).mockImplementation(
      async (_conversationId: string, _content: string, handlers: StreamHandlers) => {
        handlers.onToken?.(NOT_FOUND_MESSAGE)
        handlers.onCitations?.([])
      },
    )

    const { result } = renderHook(() => useStreamingAnswer())

    await act(async () => {
      await result.current.send('conversation-1', 'What is the CEO salary?')
    })

    expect(result.current.isNotFound).toBe(true)
  })

  it('surfaces a mid-stream error event', async () => {
    vi.mocked(streamApi.streamMessage).mockImplementation(
      async (_conversationId: string, _content: string, handlers: StreamHandlers) => {
        handlers.onError?.('Question exceeds maximum length')
      },
    )

    const { result } = renderHook(() => useStreamingAnswer())

    await act(async () => {
      await result.current.send('conversation-1', 'hi')
    })

    expect(result.current.status).toBe('error')
    expect(result.current.error).toBe('Question exceeds maximum length')
  })
})
