"""Document upload/list/get/status/delete. See specs/API.md §2."""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, status

from app.core.deps import CurrentUserIdDep
from app.core.di import get_document_service, get_ingestion_service
from app.domain.exceptions import DocumentNotFoundError
from app.schemas.document import (
    DocumentDetailResponse,
    DocumentListItem,
    DocumentListResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
)
from app.services.document_service import DocumentService
from app.services.ingestion_service import IngestionService

router = APIRouter(prefix="/documents", tags=["documents"])

DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]
IngestionServiceDep = Annotated[IngestionService, Depends(get_ingestion_service)]


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    document_service: DocumentServiceDep,
    ingestion_service: IngestionServiceDep,
    user_id: CurrentUserIdDep,
) -> DocumentUploadResponse:
    if file.filename is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing file")

    file_bytes = await file.read()
    document = await document_service.upload(
        user_id=user_id, original_filename=file.filename, file_bytes=file_bytes
    )

    background_tasks.add_task(ingestion_service.process, document.id, user_id=user_id)

    return DocumentUploadResponse.model_validate(document)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    document_service: DocumentServiceDep,
    user_id: CurrentUserIdDep,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentListResponse:
    items, total = await document_service.list(
        user_id=user_id, status=status_filter, limit=limit, offset=offset
    )
    return DocumentListResponse(
        items=[DocumentListItem.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: uuid.UUID, document_service: DocumentServiceDep, user_id: CurrentUserIdDep
) -> DocumentDetailResponse:
    document = await document_service.get(document_id, user_id=user_id)
    if document is None:
        raise DocumentNotFoundError("Document not found")
    return DocumentDetailResponse.model_validate(document)


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: uuid.UUID, document_service: DocumentServiceDep, user_id: CurrentUserIdDep
) -> DocumentStatusResponse:
    document = await document_service.get(document_id, user_id=user_id)
    if document is None:
        raise DocumentNotFoundError("Document not found")
    return DocumentStatusResponse.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID, document_service: DocumentServiceDep, user_id: CurrentUserIdDep
) -> None:
    deleted = await document_service.delete(document_id, user_id=user_id)
    if not deleted:
        raise DocumentNotFoundError("Document not found")
