// Mirrors backend/app/schemas/*.py. See specs/API.md.

export type DocumentStatusValue = 'pending' | 'processing' | 'completed' | 'failed'

export interface DocumentListItem {
  id: string
  original_filename: string
  status: DocumentStatusValue
  page_count: number | null
  created_at: string
}

export interface DocumentDetail extends DocumentListItem {
  content_type: string
  file_size_bytes: number
  error_message: string | null
  updated_at: string
}

export interface DocumentUploadResponse {
  id: string
  original_filename: string
  content_type: string
  file_size_bytes: number
  status: DocumentStatusValue
  created_at: string
}

export interface DocumentStatusResponse {
  id: string
  status: DocumentStatusValue
  error_message: string | null
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface ConversationListItem {
  id: string
  title: string | null
  created_at: string
  updated_at: string
}

export interface Conversation {
  id: string
  title: string | null
  document_ids: string[]
  created_at: string
}

export interface ConversationDetail extends Conversation {
  updated_at: string
}

export interface Citation {
  document_id: string
  document_name: string
  page_number: number | null
  chunk_id: string
  similarity_score: number
  rank: number
}

export type MessageRole = 'user' | 'assistant'

export interface Message {
  id: string
  role: MessageRole
  content: string
  created_at: string
  citations?: Citation[] | null
}

export interface MessageListResponse {
  items: Message[]
  total: number
}

export interface RegisterResponse {
  id: string
  email: string
  full_name: string | null
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
}
