import { apiFetch } from './client'
import type {
  Conversation,
  ConversationDetail,
  ConversationListItem,
  MessageListResponse,
  PaginatedResponse,
} from '../types/api'

export function createConversation(documentIds: string[] = []): Promise<Conversation> {
  return apiFetch('/conversations', {
    method: 'POST',
    body: JSON.stringify({ document_ids: documentIds }),
  })
}

export function listConversations(
  params: { limit?: number; offset?: number } = {},
): Promise<PaginatedResponse<ConversationListItem>> {
  const query = new URLSearchParams()
  if (params.limit) query.set('limit', String(params.limit))
  if (params.offset) query.set('offset', String(params.offset))
  const qs = query.toString()
  return apiFetch(`/conversations${qs ? `?${qs}` : ''}`)
}

export function getConversation(id: string): Promise<ConversationDetail> {
  return apiFetch(`/conversations/${id}`)
}

export function listMessages(
  id: string,
  params: { limit?: number; offset?: number } = {},
): Promise<MessageListResponse> {
  const query = new URLSearchParams()
  if (params.limit) query.set('limit', String(params.limit))
  if (params.offset) query.set('offset', String(params.offset))
  const qs = query.toString()
  return apiFetch(`/conversations/${id}/messages${qs ? `?${qs}` : ''}`)
}
