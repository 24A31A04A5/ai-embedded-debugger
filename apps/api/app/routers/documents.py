from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.project import Project
from app.models.user import User
from app.schemas.document import (
    DocumentChunkResponse,
    DocumentDetailResponse,
    DocumentResponse,
    DocumentSearchRequest,
    DocumentSearchResponse,
)
from app.services.document_extraction import DocumentExtractionError, DocumentExtractionService
from app.services.document_processing import DocumentProcessingService
from app.services.embedding import EmbeddingError
from app.services.retrieval import DocumentRetrievalService
from app.services.storage import BaseStorageService, get_storage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["documents"])


def get_retrieval_service(
    db: Annotated[Session, Depends(get_db)],
) -> DocumentRetrievalService:
    """Dependency: return a DocumentRetrievalService instance."""
    return DocumentRetrievalService(db)


def get_project_for_user(
    project_id: uuid.UUID | str,
    current_user: User,
    db: Session,
) -> Project:
    """Verify that a project exists and is owned by the current authenticated user."""
    try:
        proj_uuid = uuid.UUID(str(project_id))
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        ) from err

    project = (
        db.query(Project)
        .filter(Project.id == proj_uuid, Project.owner_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


@router.post(
    "/{project_id}/documents/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    project_id: str,
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    version: Annotated[str | None, Form()] = None,
    storage: Annotated[BaseStorageService, Depends(get_storage_service)] = None,  # type: ignore[assignment]
) -> DocumentResponse:
    """Upload a PDF datasheet/manual for a project and extract its text content."""
    project = get_project_for_user(project_id, current_user, db)
    settings = get_settings()

    original_filename = file.filename or "document.pdf"
    file_ext = Path(original_filename).suffix.lower()

    if file_ext != ".pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{file_ext}'. Only '.pdf' documents are supported.",
        )

    # Read content and enforce size limits
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Document exceeds maximum allowed size of {settings.max_upload_size_mb} MB",
        )

    checksum = hashlib.sha256(content).hexdigest()
    doc_id = uuid.uuid4()
    safe_filename = Path(original_filename).name
    storage_key = f"projects/{project.id}/documents/{doc_id}_{safe_filename}"

    # Upload original PDF to object storage
    storage.upload_file(
        storage_key=storage_key,
        data=content,
        content_type=file.content_type or "application/pdf",
    )

    now = datetime.now(UTC)
    doc = Document(
        id=doc_id,
        project_id=project.id,
        filename=safe_filename,
        version=version,
        size_bytes=len(content),
        checksum=checksum,
        storage_key=storage_key,
        extraction_status="processing",
        created_at=now,
        updated_at=now,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Execute text extraction
    try:
        extraction_res = DocumentExtractionService.extract_pdf_content(content)
        doc.extracted_text = extraction_res.text
        doc.page_count = extraction_res.page_count
        doc.metadata_json = extraction_res.metadata

        # Phase 3.2: chunk and generate embeddings
        try:
            processor = DocumentProcessingService(db)
            processor.process_document(
                document=doc,
                extracted_text=extraction_res.text,
                page_texts=extraction_res.page_texts,
            )
            doc.extraction_status = "ready"
            doc.error_message = None
        except EmbeddingError as emb_err:
            # Extraction succeeded but embedding failed — mark as ready
            # but record the embedding error so it can be retried
            logger.warning("Embedding failed for document %s: %s", doc.id, emb_err)
            doc.extraction_status = "ready"
            doc.error_message = f"Text extracted but embedding failed: {emb_err}"
        except Exception as proc_err:
            logger.warning("Document processing failed for %s: %s", doc.id, proc_err)
            doc.extraction_status = "ready"
            doc.error_message = f"Text extracted but chunking/embedding failed: {proc_err}"

    except DocumentExtractionError as err:
        doc.extraction_status = "failed"
        doc.error_message = str(err)
    except Exception as err:
        doc.extraction_status = "failed"
        doc.error_message = f"Unexpected extraction error: {err}"

    doc.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(doc)

    download_url = storage.get_download_url(storage_key)
    res = DocumentResponse.model_validate(doc)
    res.download_url = download_url
    return res


@router.get("/{project_id}/documents", response_model=list[DocumentResponse])
def list_project_documents(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[BaseStorageService, Depends(get_storage_service)] = None,  # type: ignore[assignment]
) -> list[DocumentResponse]:
    """List all uploaded documents for a project."""
    project = get_project_for_user(project_id, current_user, db)

    documents = (
        db.query(Document)
        .filter(Document.project_id == project.id)
        .order_by(Document.created_at.desc())
        .all()
    )

    results: list[DocumentResponse] = []
    for doc in documents:
        res = DocumentResponse.model_validate(doc)
        res.download_url = storage.get_download_url(doc.storage_key)
        results.append(res)

    return results


@router.get("/{project_id}/documents/{document_id}", response_model=DocumentDetailResponse)
def get_project_document(
    project_id: str,
    document_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[BaseStorageService, Depends(get_storage_service)] = None,  # type: ignore[assignment]
) -> DocumentDetailResponse:
    """Retrieve metadata and extracted text details for a single document."""
    project = get_project_for_user(project_id, current_user, db)

    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        ) from err

    doc = (
        db.query(Document)
        .filter(Document.id == doc_uuid, Document.project_id == project.id)
        .first()
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    res = DocumentDetailResponse.model_validate(doc)
    res.download_url = storage.get_download_url(doc.storage_key)
    res.text_length = len(doc.extracted_text or "")
    return res


@router.get(
    "/{project_id}/documents/{document_id}/chunks",
    response_model=list[DocumentChunkResponse],
)
def list_document_chunks(
    project_id: str,
    document_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[DocumentChunkResponse]:
    """List all chunks for a document, ordered by chunk_index."""
    project = get_project_for_user(project_id, current_user, db)

    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        ) from err

    doc = (
        db.query(Document)
        .filter(Document.id == doc_uuid, Document.project_id == project.id)
        .first()
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == doc.id)
        .order_by(DocumentChunk.chunk_index)
        .all()
    )

    results: list[DocumentChunkResponse] = []
    for chunk in chunks:
        resp = DocumentChunkResponse.model_validate(chunk)
        resp.has_embedding = chunk.embedding is not None
        results.append(resp)

    return results


@router.delete("/{project_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_document(
    project_id: str,
    document_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[BaseStorageService, Depends(get_storage_service)] = None,  # type: ignore[assignment]
) -> Response:
    """Delete a document from both object storage and the database."""
    project = get_project_for_user(project_id, current_user, db)

    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        ) from err

    doc = (
        db.query(Document)
        .filter(Document.id == doc_uuid, Document.project_id == project.id)
        .first()
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    storage.delete_file(doc.storage_key)
    db.delete(doc)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{project_id}/documents/search",
    response_model=DocumentSearchResponse,
)
def search_project_documents(
    project_id: str,
    body: DocumentSearchRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    retrieval: Annotated[DocumentRetrievalService, Depends(get_retrieval_service)],
) -> DocumentSearchResponse:
    """Search for relevant document chunks within a user's project using vector similarity."""
    project = get_project_for_user(project_id, current_user, db)

    try:
        search_kwargs: dict[str, Any] = {
            "project_id": project.id,
            "query": body.query,
            "top_k": body.top_k,
            "similarity_threshold": body.similarity_threshold,
            "document_ids": body.document_ids,
        }
        if body.section is not None:
            search_kwargs["section"] = body.section
        if body.content_type is not None:
            search_kwargs["content_type"] = body.content_type
        if body.page_number is not None:
            search_kwargs["page_number"] = body.page_number
        if body.has_register is not None:
            search_kwargs["has_register"] = body.has_register
        if body.has_table is not None:
            search_kwargs["has_table"] = body.has_table
        if body.has_pinout is not None:
            search_kwargs["has_pinout"] = body.has_pinout

        results = retrieval.search(**search_kwargs)
    except EmbeddingError as err:


        logger.error("Failed to generate embedding for query in project %s: %s", project.id, err)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Embedding service failure: {err}",
        ) from err
    except Exception as err:
        logger.error("Vector retrieval failed for project %s: %s", project.id, err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute document search",
        ) from err

    return DocumentSearchResponse(
        query=body.query,
        results=results,
        total_results=len(results),
    )

