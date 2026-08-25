import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { createConversation, listConversations, listMessages } from '../api/conversations'
import { listDocuments } from '../api/documents'
import { useStreamingAnswer } from '../hooks/useStreamingAnswer'
import { NOT_FOUND_MESSAGE } from '../constants'
import type { ConversationListItem, DocumentListItem, Message } from '../types/api'
import { CitationCard } from './CitationCard'

interface ChatWindowProps {
  documentsVersion: number
}

export function ChatWindow({ documentsVersion }: ChatWindowProps) {
  const [conversations, setConversations] = useState<ConversationListItem[]>([])
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [documents, setDocuments] = useState<DocumentListItem[]>([])
  const [isPickerOpen, setPickerOpen] = useState(false)
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([])
  const [input, setInput] = useState('')
  const [loadError, setLoadError] = useState<string | null>(null)

  const {
    status: streamStatus,
    content: streamContent,
    citations: streamCitations,
    error: streamError,
    isNotFound,
    send: sendMessage,
    reset: resetStreaming,
  } = useStreamingAnswer()

  const refreshConversations = useCallback(async () => {
    const response = await listConversations({ limit: 50 })
    setConversations(response.items)
  }, [])

  useEffect(() => {
    let cancelled = false
    async function load() {
      const response = await listConversations({ limit: 50 })
      if (!cancelled) setConversations(response.items)
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    void listDocuments({ limit: 100 }).then((response) => setDocuments(response.items))
  }, [documentsVersion])

  const loadMessages = useCallback(async (conversationId: string) => {
    const response = await listMessages(conversationId, { limit: 100 })
    setMessages(response.items)
  }, [])

  async function handleSelectConversation(id: string) {
    setActiveConversationId(id)
    setPickerOpen(false)
    setLoadError(null)
    resetStreaming()
    try {
      await loadMessages(id)
    } catch {
      setLoadError('Could not load this conversation.')
    }
  }

  async function handleCreateConversation() {
    const conversation = await createConversation(selectedDocumentIds)
    setPickerOpen(false)
    setSelectedDocumentIds([])
    await refreshConversations()
    setActiveConversationId(conversation.id)
    setMessages([])
    resetStreaming()
  }

  async function handleSend(event: FormEvent) {
    event.preventDefault()
    const question = input.trim()
    if (!activeConversationId || !question || streamStatus === 'streaming') return

    setMessages((prev) => [
      ...prev,
      { id: `local-${prev.length}`, role: 'user', content: question, created_at: new Date().toISOString() },
    ])
    setInput('')
    await sendMessage(activeConversationId, question)
  }

  // Once the stream finishes, reload from the server so the persisted
  // message (with its real ID and citations) replaces the local echo.
  useEffect(() => {
    if (streamStatus !== 'done' || !activeConversationId) return undefined
    const conversationId = activeConversationId
    let cancelled = false
    async function reload() {
      const response = await listMessages(conversationId, { limit: 100 })
      if (cancelled) return
      setMessages(response.items)
      resetStreaming()
    }
    void reload()
    return () => {
      cancelled = true
    }
  }, [streamStatus, activeConversationId, resetStreaming])

  function toggleDocumentSelection(id: string) {
    setSelectedDocumentIds((prev) =>
      prev.includes(id) ? prev.filter((existing) => existing !== id) : [...prev, id],
    )
  }

  return (
    <div className="flex h-full gap-4">
      <aside className="flex w-56 shrink-0 flex-col gap-2 border-r border-neutral-200 pr-4">
        <button
          type="button"
          onClick={() => setPickerOpen(true)}
          className="rounded bg-neutral-900 px-3 py-2 text-sm font-medium text-white"
        >
          New conversation
        </button>
        <ul className="flex flex-col gap-1 overflow-y-auto">
          {conversations.map((conversation) => (
            <li key={conversation.id}>
              <button
                type="button"
                onClick={() => void handleSelectConversation(conversation.id)}
                className={`w-full truncate rounded px-2 py-1 text-left text-sm ${
                  activeConversationId === conversation.id
                    ? 'bg-neutral-200 text-neutral-900'
                    : 'text-neutral-600 hover:bg-neutral-100'
                }`}
              >
                {conversation.title ?? 'Untitled conversation'}
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <section className="flex flex-1 flex-col">
        {isPickerOpen && (
          <div className="mb-3 rounded border border-neutral-200 p-3">
            <p className="mb-2 text-sm font-medium">
              Scope this conversation to specific documents (optional - leave empty to search all
              of your completed documents).
            </p>
            <ul className="mb-3 flex max-h-40 flex-col gap-1 overflow-y-auto">
              {documents.map((doc) => (
                <li key={doc.id} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={selectedDocumentIds.includes(doc.id)}
                    onChange={() => toggleDocumentSelection(doc.id)}
                    aria-label={`Scope to ${doc.original_filename}`}
                  />
                  {doc.original_filename}
                </li>
              ))}
              {documents.length === 0 && (
                <li className="text-xs text-neutral-400">Upload a document first.</li>
              )}
            </ul>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => void handleCreateConversation()}
                className="rounded bg-neutral-900 px-3 py-1.5 text-sm text-white"
              >
                Start
              </button>
              <button
                type="button"
                onClick={() => setPickerOpen(false)}
                className="rounded border border-neutral-300 px-3 py-1.5 text-sm"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {!activeConversationId && !isPickerOpen && (
          <p className="text-sm text-neutral-400">Select a conversation or start a new one.</p>
        )}

        {activeConversationId && (
          <>
            <div className="flex-1 overflow-y-auto rounded border border-neutral-200 p-4">
              {loadError && <p className="text-sm text-red-600">{loadError}</p>}
              <ul className="flex flex-col gap-3">
                {messages.map((message) => {
                  const messageIsNotFound = message.content === NOT_FOUND_MESSAGE
                  return (
                    <li key={message.id} className={message.role === 'user' ? 'text-right' : 'text-left'}>
                      <div
                        className={`inline-block max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                          message.role === 'user'
                            ? 'bg-neutral-900 text-white'
                            : messageIsNotFound
                              ? 'border border-amber-300 bg-amber-50 text-amber-800'
                              : 'bg-neutral-100 text-neutral-900'
                        }`}
                      >
                        {message.content}
                      </div>
                      {message.citations && message.citations.length > 0 && (
                        <div className="mt-1 flex flex-col gap-1">
                          {message.citations.map((citation) => (
                            <CitationCard key={citation.chunk_id} citation={citation} />
                          ))}
                        </div>
                      )}
                    </li>
                  )
                })}

                {streamStatus !== 'idle' && (
                  <li className="text-left">
                    <div
                      data-testid="streaming-message"
                      className={`inline-block max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                        isNotFound
                          ? 'border border-amber-300 bg-amber-50 text-amber-800'
                          : 'bg-neutral-100 text-neutral-900'
                      }`}
                    >
                      {streamContent || (streamStatus === 'streaming' ? 'Thinking...' : '')}
                      {streamStatus === 'error' && <span className="text-red-600"> {streamError}</span>}
                    </div>
                    {streamCitations.length > 0 && (
                      <div className="mt-1 flex flex-col gap-1">
                        {streamCitations.map((citation) => (
                          <CitationCard key={citation.chunk_id} citation={citation} />
                        ))}
                      </div>
                    )}
                  </li>
                )}
              </ul>
            </div>

            <form onSubmit={handleSend} className="mt-3 flex gap-2">
              <input
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="Ask a question about your documents..."
                aria-label="Question"
                className="flex-1 rounded border border-neutral-300 px-3 py-2 text-sm"
                maxLength={2000}
              />
              <button
                type="submit"
                disabled={streamStatus === 'streaming' || !input.trim()}
                className="rounded bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                Send
              </button>
            </form>
          </>
        )}
      </section>
    </div>
  )
}
