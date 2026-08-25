// SSE consumer for POST /conversations/{id}/messages (specs/API.md §3).
// EventSource can't be used: it only supports GET and can't set an
// Authorization header, so the stream is parsed by hand off a fetch()
// ReadableStream instead.

import { API_BASE, ApiError, getToken } from './client'
import type { Citation } from '../types/api'

export interface StreamHandlers {
  onToken?: (content: string) => void
  onCitations?: (citations: Citation[]) => void
  onDone?: (messageId: string) => void
  onError?: (detail: string) => void
}

export async function streamMessage(
  conversationId: string,
  content: string,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const token = getToken()
  const response = await fetch(`${API_BASE}/conversations/${conversationId}/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ content }),
    signal,
  })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      if (typeof body?.detail === 'string') detail = body.detail
    } catch {
      // Response wasn't JSON - fall back to statusText.
    }
    throw new ApiError(detail, response.status)
  }

  if (!response.body) {
    throw new Error('Streaming is not supported in this environment.')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let separatorIndex = buffer.indexOf('\n\n')
    while (separatorIndex !== -1) {
      dispatchFrame(buffer.slice(0, separatorIndex), handlers)
      buffer = buffer.slice(separatorIndex + 2)
      separatorIndex = buffer.indexOf('\n\n')
    }
  }
}

function dispatchFrame(rawFrame: string, handlers: StreamHandlers): void {
  let eventName = 'message'
  const dataLines: string[] = []
  for (const line of rawFrame.split('\n')) {
    if (line.startsWith('event:')) {
      eventName = line.slice('event:'.length).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trim())
    }
  }
  if (dataLines.length === 0) return

  let payload: Record<string, unknown>
  try {
    payload = JSON.parse(dataLines.join('\n'))
  } catch {
    return
  }

  switch (eventName) {
    case 'token':
      if (typeof payload.content === 'string') handlers.onToken?.(payload.content)
      break
    case 'citations':
      if (Array.isArray(payload.citations)) handlers.onCitations?.(payload.citations as Citation[])
      break
    case 'done':
      if (typeof payload.message_id === 'string') handlers.onDone?.(payload.message_id)
      break
    case 'error':
      if (typeof payload.detail === 'string') handlers.onError?.(payload.detail)
      break
    default:
      break
  }
}
