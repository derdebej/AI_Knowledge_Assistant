"""Request/response DTOs for the conversations API. See specs/API.md §3.

`Conversation.documents` (a list of ORM `Document` objects) doesn't map
1:1 onto the wire shape's `document_ids: list[UUID]` via `from_attributes`,
so these are built explicitly in `app/api/v1/chat.py` rather than via
`model_validate` - see specs/ARCHITECTURE.md §2.2 on schemas being decoupled
from ORM models.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreateRequest(BaseModel):
    document_ids: list[uuid.UUID] = Field(default_factory=list)


class ConversationResponse(BaseModel):
    id: uuid.UUID
    title: str | None
    document_ids: list[uuid.UUID]
    created_at: datetime


class ConversationListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    items: list[ConversationListItem]
    total: int
    limit: int
    offset: int


class ConversationDetailResponse(BaseModel):
    id: uuid.UUID
    title: str | None
    document_ids: list[uuid.UUID]
    created_at: datetime
    updated_at: datetime
