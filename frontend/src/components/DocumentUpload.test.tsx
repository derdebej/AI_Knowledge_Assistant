import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DocumentUpload } from './DocumentUpload'
import * as documentsApi from '../api/documents'
import { MAX_UPLOAD_SIZE_BYTES } from '../constants'

vi.mock('../api/documents')

function makeFile(name: string, sizeBytes: number, type: string): File {
  const file = new File([new Uint8Array(Math.max(sizeBytes, 1))], name, { type })
  Object.defineProperty(file, 'size', { value: sizeBytes })
  return file
}

describe('DocumentUpload', () => {
  beforeEach(() => {
    vi.mocked(documentsApi.uploadDocument).mockReset()
  })

  it('rejects an unsupported extension without calling the API', async () => {
    const onUploaded = vi.fn()
    render(<DocumentUpload onUploaded={onUploaded} />)

    const input = screen.getByLabelText('Upload document')
    const file = makeFile('malware.exe', 1024, 'application/octet-stream')
    // The real browser's `accept` filtering would already stop this file at
    // the picker - applyAccept:false exercises our own validation logic
    // underneath that, which is what actually enforces the rule server-side too.
    await userEvent.upload(input, file, { applyAccept: false })

    expect(await screen.findByRole('alert')).toHaveTextContent(/unsupported file type/i)
    expect(documentsApi.uploadDocument).not.toHaveBeenCalled()
    expect(onUploaded).not.toHaveBeenCalled()
  })

  it('rejects a file over the size limit without calling the API', async () => {
    const onUploaded = vi.fn()
    render(<DocumentUpload onUploaded={onUploaded} />)

    const input = screen.getByLabelText('Upload document')
    const file = makeFile('big.pdf', MAX_UPLOAD_SIZE_BYTES + 1, 'application/pdf')
    await userEvent.upload(input, file)

    expect(await screen.findByRole('alert')).toHaveTextContent(/exceeds the 20 MB limit/i)
    expect(documentsApi.uploadDocument).not.toHaveBeenCalled()
  })

  it('uploads a valid file and reports the result', async () => {
    const onUploaded = vi.fn()
    vi.mocked(documentsApi.uploadDocument).mockResolvedValue({
      id: 'doc-1',
      original_filename: 'report.pdf',
      content_type: 'application/pdf',
      file_size_bytes: 2048,
      status: 'pending',
      created_at: new Date().toISOString(),
    })

    render(<DocumentUpload onUploaded={onUploaded} />)
    const input = screen.getByLabelText('Upload document')
    const file = makeFile('report.pdf', 2048, 'application/pdf')
    await userEvent.upload(input, file)

    await waitFor(() => expect(onUploaded).toHaveBeenCalledTimes(1))
    expect(documentsApi.uploadDocument).toHaveBeenCalledWith(file, expect.any(Function))
  })
})
