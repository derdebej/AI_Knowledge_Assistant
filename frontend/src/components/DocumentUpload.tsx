import { useCallback, useRef, useState } from 'react'
import type { DragEvent } from 'react'
import { ApiError } from '../api/client'
import { uploadDocument } from '../api/documents'
import { ALLOWED_UPLOAD_EXTENSIONS, MAX_UPLOAD_SIZE_BYTES } from '../constants'
import type { DocumentUploadResponse } from '../types/api'

interface DocumentUploadProps {
  onUploaded: (document: DocumentUploadResponse) => void
}

// Mirrors backend/app/documents/validation.py so obviously-invalid files
// are rejected before a round trip - the server still re-validates.
function validateFile(file: File): string | null {
  const extension = file.name.includes('.') ? `.${file.name.split('.').pop()!.toLowerCase()}` : ''
  if (!ALLOWED_UPLOAD_EXTENSIONS.includes(extension)) {
    return `Unsupported file type "${extension || 'unknown'}". Allowed: ${ALLOWED_UPLOAD_EXTENSIONS.join(', ')}.`
  }
  if (file.size === 0) {
    return 'File is empty.'
  }
  if (file.size > MAX_UPLOAD_SIZE_BYTES) {
    return `File exceeds the ${MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)} MB limit.`
  }
  return null
}

export function DocumentUpload({ onUploaded }: DocumentUploadProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [progress, setProgress] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const startUpload = useCallback(
    async (file: File) => {
      setError(null)
      const validationError = validateFile(file)
      if (validationError) {
        setError(validationError)
        return
      }
      setProgress(0)
      try {
        const document = await uploadDocument(file, setProgress)
        onUploaded(document)
      } catch (err) {
        setError(err instanceof ApiError ? err.message : 'Upload failed. Please try again.')
      } finally {
        setProgress(null)
      }
    },
    [onUploaded],
  )

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setIsDragging(false)
    const file = event.dataTransfer.files[0]
    if (file) void startUpload(file)
  }

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        data-testid="dropzone"
        onDragOver={(event) => {
          event.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') inputRef.current?.click()
        }}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 text-center text-sm transition-colors ${
          isDragging ? 'border-neutral-900 bg-neutral-100' : 'border-neutral-300 text-neutral-500'
        }`}
      >
        <p>Drag and drop a PDF or TXT file here, or click to browse.</p>
        <p className="mt-1 text-xs text-neutral-400">Max 20 MB - .pdf, .txt</p>
        <input
          ref={inputRef}
          type="file"
          aria-label="Upload document"
          accept={ALLOWED_UPLOAD_EXTENSIONS.join(',')}
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0]
            event.target.value = ''
            if (file) void startUpload(file)
          }}
        />
      </div>
      {progress !== null && (
        <div
          className="mt-2 h-2 w-full overflow-hidden rounded bg-neutral-200"
          role="progressbar"
          aria-valuenow={progress}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div className="h-full bg-neutral-900 transition-all" style={{ width: `${progress}%` }} />
        </div>
      )}
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  )
}
