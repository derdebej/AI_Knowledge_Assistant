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
        className={`group relative flex cursor-pointer flex-col items-center justify-center overflow-hidden rounded-2xl border-2 border-dashed p-6 text-center transition-all duration-200 ${
          isDragging
            ? 'scale-[1.02] border-violet-400 bg-violet-500/10 shadow-lg shadow-violet-500/10'
            : 'border-white/15 bg-white/[0.02] hover:border-white/25 hover:bg-white/[0.04]'
        }`}
      >
        <div
          className={`mb-2.5 flex h-10 w-10 items-center justify-center rounded-xl transition-all duration-200 ${
            isDragging ? 'scale-110 bg-violet-500/20' : 'bg-white/5 group-hover:bg-white/10'
          }`}
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            className={`h-5 w-5 transition-colors ${isDragging ? 'text-violet-300' : 'text-slate-400'}`}
          >
            <path
              d="M12 16V4m0 0L7 9m5-5l5 5M5 20h14"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <p className="text-sm font-medium text-slate-200">
          {isDragging ? 'Drop to upload' : 'Drag & drop a file'}
        </p>
        <p className="mt-1 text-xs text-slate-500">
          or <span className="text-violet-400">browse</span> · PDF or TXT, max 20 MB
        </p>
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
        <div className="mt-3 animate-fade-in">
          <div className="mb-1 flex items-center justify-between text-xs text-slate-400">
            <span>Uploading...</span>
            <span>{progress}%</span>
          </div>
          <div
            className="h-1.5 w-full overflow-hidden rounded-full bg-white/5"
            role="progressbar"
            aria-valuenow={progress}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className="h-full rounded-full bg-gradient-to-r from-violet-500 to-blue-500 transition-all duration-200"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}
      {error && (
        <p role="alert" className="mt-2 animate-fade-in rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {error}
        </p>
      )}
    </div>
  )
}
