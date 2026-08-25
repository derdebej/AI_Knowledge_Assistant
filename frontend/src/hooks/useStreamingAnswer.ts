import { useCallback, useRef, useState } from 'react'
import { streamMessage } from '../api/stream'
import { NOT_FOUND_MESSAGE } from '../constants'
import type { Citation } from '../types/api'

export type StreamingStatus = 'idle' | 'streaming' | 'done' | 'error'

export interface StreamingAnswerState {
  status: StreamingStatus
  content: string
  citations: Citation[]
  messageId: string | null
  error: string | null
}

const initialState: StreamingAnswerState = {
  status: 'idle',
  content: '',
  citations: [],
  messageId: null,
  error: null,
}

export function useStreamingAnswer() {
  const [state, setState] = useState<StreamingAnswerState>(initialState)
  const abortRef = useRef<AbortController | null>(null)

  const send = useCallback(async (conversationId: string, content: string) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setState({ status: 'streaming', content: '', citations: [], messageId: null, error: null })

    try {
      await streamMessage(
        conversationId,
        content,
        {
          onToken: (token) => setState((prev) => ({ ...prev, content: prev.content + token })),
          onCitations: (citations) => setState((prev) => ({ ...prev, citations })),
          onDone: (messageId) => setState((prev) => ({ ...prev, status: 'done', messageId })),
          onError: (detail) => setState((prev) => ({ ...prev, status: 'error', error: detail })),
        },
        controller.signal,
      )
    } catch (err) {
      if (controller.signal.aborted) return
      setState((prev) => ({
        ...prev,
        status: 'error',
        error: err instanceof Error ? err.message : 'Failed to reach the server.',
      }))
    }
  }, [])

  const reset = useCallback(() => setState(initialState), [])

  const isNotFound = state.content.trim() === NOT_FOUND_MESSAGE && state.citations.length === 0

  return { ...state, isNotFound, send, reset }
}
