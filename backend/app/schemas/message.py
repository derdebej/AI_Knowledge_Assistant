"""Request/response DTOs for the messages API. See specs/API.md §3.

`CitationResponse`/`MessageResponse` are built explicitly in
`app/api/v1/chat.py` from ORM rows (a `Message` plus its `MessageCitation`s
joined through to their `DocumentChunk`), not via `model_validate` - the
wire shape (`document_id`, `document_name`, `page_number`) doesn't map 1:1
onto any single ORM model's attributes.
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

# Max length mirrors specs/RAG_PIPELINE.md §2.1 (question validation) - a
# too-long question is rejected with 422 before any embedding call is made.
MessageContent = Annotated[str, Field(min_length=1, max_length=2000)]


class MessageCreateRequest(BaseModel):
    content: MessageContent


class CitationResponse(BaseModel):
    document_id: uuid.UUID
    document_name: str
    page_number: int | None
    chunk_id: uuid.UUID
    similarity_score: float
    rank: int


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    citations: list[CitationResponse] | None = None


class MessageListResponse(BaseModel):
    items: list[MessageResponse]
    total: int
