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
    <div className="flex h-full">
      <aside className="flex w-60 shrink-0 flex-col gap-1.5 border-r border-white/10 p-3">
        <button
          type="button"
          onClick={() => setPickerOpen(true)}
          className="mb-2 flex items-center justify-center gap-1.5 rounded-lg bg-gradient-to-r from-violet-600 to-blue-600 px-3 py-2 text-sm font-medium text-white shadow-md shadow-violet-600/20 transition-all hover:brightness-110 active:scale-[0.98]"
        >
          <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4">
            <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          New conversation
        </button>
        <ul className="flex flex-1 flex-col gap-0.5 overflow-y-auto">
          {conversations.map((conversation) => (
            <li key={conversation.id}>
              <button
                type="button"
                onClick={() => void handleSelectConversation(conversation.id)}
                className={`w-full truncate rounded-lg px-2.5 py-2 text-left text-sm transition-colors ${
                  activeConversationId === conversation.id
                    ? 'bg-white/[0.08] text-white'
                    : 'text-slate-400 hover:bg-white/[0.04] hover:text-slate-200'
                }`}
              >
                {conversation.title ?? 'Untitled conversation'}
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <section className="flex flex-1 flex-col p-4">
        {isPickerOpen && (
          <div className="mb-3 animate-fade-in-up rounded-xl border border-white/10 bg-white/[0.03] p-4">
            <p className="mb-3 text-sm text-slate-300">
              Scope this conversation to specific documents{' '}
              <span className="text-slate-500">(optional — leave empty to search all of your completed documents)</span>
            </p>
            <ul className="mb-3 flex max-h-40 flex-col gap-1 overflow-y-auto">
              {documents.map((doc) => (
                <li key={doc.id}>
                  <label className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm text-slate-300 hover:bg-white/[0.04]">
                    <input
                      type="checkbox"
                      checked={selectedDocumentIds.includes(doc.id)}
                      onChange={() => toggleDocumentSelection(doc.id)}
                      aria-label={`Scope to ${doc.original_filename}`}
                      className="h-3.5 w-3.5 accent-violet-500"
                    />
                    {doc.original_filename}
                  </label>
                </li>
              ))}
              {documents.length === 0 && (
                <li className="px-2 py-1 text-xs text-slate-500">Upload a document first.</li>
              )}
            </ul>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => void handleCreateConversation()}
                className="rounded-lg bg-gradient-to-r from-violet-600 to-blue-600 px-3.5 py-1.5 text-sm font-medium text-white transition-all hover:brightness-110 active:scale-[0.98]"
              >
                Start
              </button>
              <button
                type="button"
                onClick={() => setPickerOpen(false)}
                className="rounded-lg border border-white/10 px-3.5 py-1.5 text-sm text-slate-300 transition-colors hover:bg-white/[0.05]"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {!activeConversationId && !isPickerOpen && (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white/[0.03]">
              <svg viewBox="0 0 24 24" fill="none" className="h-7 w-7 text-slate-600">
                <path
                  d="M8 10h8M8 14h5M21 12c0 4.418-4.03 8-9 8-1.06 0-2.077-.163-3.02-.463L3 21l1.5-4.5C3.55 15.077 3 13.582 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <p className="text-sm text-slate-500">Select a conversation or start a new one.</p>
          </div>
        )}

        {activeConversationId && (
          <>
            <div className="flex-1 space-y-3 overflow-y-auto rounded-xl border border-white/10 bg-black/10 p-4">
              {loadError && <p className="text-sm text-red-400">{loadError}</p>}
              <ul className="flex flex-col gap-4">
                {messages.map((message) => {
                  const messageIsNotFound = message.content === NOT_FOUND_MESSAGE
                  return (
                    <li
                      key={message.id}
                      className={`animate-fade-in-up ${message.role === 'user' ? 'text-right' : 'text-left'}`}
                    >
                      <div
                        className={`inline-block max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                          message.role === 'user'
                            ? 'rounded-br-md bg-gradient-to-br from-violet-600 to-blue-600 text-white shadow-md shadow-violet-600/15'
                            : messageIsNotFound
                              ? 'rounded-bl-md border border-amber-400/25 bg-amber-500/10 text-amber-200'
                              : 'rounded-bl-md bg-white/[0.06] text-slate-100'
                        }`}
                      >
                        {message.content}
                      </div>
                      {message.citations && message.citations.length > 0 && (
                        <div className="mt-1.5 flex flex-col gap-1">
                          {message.citations.map((citation) => (
                            <CitationCard key={citation.chunk_id} citation={citation} />
                          ))}
                        </div>
                      )}
                    </li>
                  )
                })}

                {streamStatus !== 'idle' && (
                  <li className="animate-fade-in-up text-left">
                    <div
                      data-testid="streaming-message"
                      className={`inline-block max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-bl-md px-4 py-2.5 text-sm leading-relaxed ${
                        isNotFound
                          ? 'border border-amber-400/25 bg-amber-500/10 text-amber-200'
                          : 'bg-white/[0.06] text-slate-100'
                      }`}
                    >
                      {streamContent || (
                        streamStatus === 'streaming' && (
                          <span className="inline-flex items-center gap-1">
                            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.3s]" />
                            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.15s]" />
                            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400" />
                          </span>
                        )
                      )}
                      {streamStatus === 'error' && <span className="text-red-400"> {streamError}</span>}
                    </div>
                    {streamCitations.length > 0 && (
                      <div className="mt-1.5 flex flex-col gap-1">
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
                className="flex-1 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2.5 text-sm text-white placeholder-slate-500 outline-none transition-all focus:border-violet-400/50 focus:bg-white/[0.06] focus:ring-2 focus:ring-violet-500/20"
                maxLength={2000}
              />
              <button
                type="submit"
                disabled={streamStatus === 'streaming' || !input.trim()}
                className="flex items-center justify-center rounded-xl bg-gradient-to-r from-violet-600 to-blue-600 px-4 py-2.5 text-sm font-medium text-white shadow-md shadow-violet-600/20 transition-all hover:brightness-110 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:brightness-100"
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
