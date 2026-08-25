// Mirrors backend/app/core/config.py defaults - not exposed by any endpoint,
// so the client-side pre-check has to hardcode the same values as the server.
export const MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024
export const ALLOWED_UPLOAD_EXTENSIONS = ['.pdf', '.txt']

// Fixed refusal string from specs/RAG_PIPELINE.md §2.6/§5 - the frontend
// pattern-matches on it to render a distinct "not found" state.
export const NOT_FOUND_MESSAGE = "I couldn't find this information in your documents."
