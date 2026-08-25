import { API_BASE, ApiError, apiFetch, getToken } from './client'
import type {
  DocumentDetail,
  DocumentListItem,
  DocumentStatusResponse,
  DocumentUploadResponse,
  PaginatedResponse,
} from '../types/api'

export function listDocuments(
  params: { status?: string; limit?: number; offset?: number } = {},
): Promise<PaginatedResponse<DocumentListItem>> {
  const query = new URLSearchParams()
  if (params.status) query.set('status', params.status)
  if (params.limit) query.set('limit', String(params.limit))
  if (params.offset) query.set('offset', String(params.offset))
  const qs = query.toString()
  return apiFetch(`/documents${qs ? `?${qs}` : ''}`)
}

export function getDocument(id: string): Promise<DocumentDetail> {
  return apiFetch(`/documents/${id}`)
}

export function getDocumentStatus(id: string): Promise<DocumentStatusResponse> {
  return apiFetch(`/documents/${id}/status`)
}

export function deleteDocument(id: string): Promise<void> {
  return apiFetch(`/documents/${id}`, { method: 'DELETE' })
}

// Uses XMLHttpRequest (not fetch) because upload progress events -
// specifically required by the roadmap's "upload progress" item - have no
// fetch equivalent for request bodies.
export function uploadDocument(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<DocumentUploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${API_BASE}/documents`)
    const token = getToken()
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100))
      }
    }

    xhr.onload = () => {
      let body: unknown = null
      try {
        body = JSON.parse(xhr.responseText)
      } catch {
        // Non-JSON body (e.g. an unhandled 500) - fall back to statusText below.
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as DocumentUploadResponse)
        return
      }
      const detail =
        body && typeof body === 'object' && 'detail' in body
          ? String((body as { detail: unknown }).detail)
          : xhr.statusText
      const errorCode =
        body && typeof body === 'object' && 'error_code' in body
          ? String((body as { error_code: unknown }).error_code)
          : undefined
      reject(new ApiError(detail, xhr.status, errorCode))
    }
    xhr.onerror = () => reject(new ApiError('Network error during upload', 0))

    const formData = new FormData()
    formData.append('file', file)
    xhr.send(formData)
  })
}
