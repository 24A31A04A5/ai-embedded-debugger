import io
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.core.auth import get_current_user
from app.core.database import get_db
from app.main import app
from app.models.document import Document
from app.models.project import Project
from app.models.user import User
from app.services.document_extraction import DocumentExtractionError, DocumentExtractionService
from app.services.storage import BaseStorageService, get_storage_service


def create_valid_pdf_bytes(text_content: str = "STM32F401 Microcontroller Datasheet") -> bytes:
    """Helper to generate valid in-memory PDF bytes with text."""
    # A standard raw minimal PDF 1.4 containing the text string
    stream = f"BT /F1 12 Tf 50 700 Td ({text_content}) Tj ET"
    stream_bytes = stream.encode("latin1")
    stream_len = len(stream_bytes)

    pdf_template = (
        f"%PDF-1.4\n"
        f"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        f"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        f"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
        f"4 0 obj << /Length {stream_len} >> stream\n"
        f"{stream}\n"
        f"endstream\n"
        f"endobj\n"
        f"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
        f"xref\n"
        f"0 6\n"
        f"0000000000 65535 f \n"
        f"0000000009 00000 n \n"
        f"0000000058 00000 n \n"
        f"0000000115 00000 n \n"
        f"0000000244 00000 n \n"
        f"0000000340 00000 n \n"
        f"trailer << /Size 6 /Root 1 0 R >>\n"
        f"startxref\n"
        f"420\n"
        f"%%EOF\n"
    )
    return pdf_template.encode("latin1")


@pytest.fixture
def mock_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="dev@example.com",
        clerk_id="user_clerk_doc",
        auth_provider="clerk",
        plan="free",
    )


@pytest.fixture
def other_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="other@example.com",
        clerk_id="user_other_doc",
        auth_provider="clerk",
        plan="free",
    )


@pytest.fixture
def mock_project(mock_user: User) -> Project:
    return Project(
        id=uuid.uuid4(),
        owner_id=mock_user.id,
        name="ESP32 Document Project",
        description="Docs Workspace",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def test_document_extraction_service_success() -> None:
    """DocumentExtractionService parses a valid PDF and returns extracted text and page count."""
    pdf_bytes = create_valid_pdf_bytes("ESP32-WROOM-32 Datasheet Pinout")
    result = DocumentExtractionService.extract_pdf_content(pdf_bytes)

    assert result.page_count == 1
    assert "ESP32-WROOM-32 Datasheet Pinout" in result.text


def test_document_extraction_service_empty_bytes() -> None:
    """DocumentExtractionService raises DocumentExtractionError for empty content."""
    with pytest.raises(DocumentExtractionError) as exc_info:
        DocumentExtractionService.extract_pdf_content(b"")

    assert "empty" in str(exc_info.value).lower()


def test_document_extraction_service_malformed_bytes() -> None:
    """DocumentExtractionService raises DocumentExtractionError for corrupt PDF data."""
    with pytest.raises(DocumentExtractionError) as exc_info:
        DocumentExtractionService.extract_pdf_content(b"NOT A REAL PDF FILE HEADER")

    assert "malformed" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()


def test_upload_valid_pdf_success(mock_user: User, mock_project: Project) -> None:
    """Uploading a valid PDF saves to storage, extracts text, and returns ready status."""
    mock_db = MagicMock()
    mock_storage = MagicMock()
    mock_storage.get_download_url.return_value = "https://example.com/download/doc.pdf"

    def _query_side_effect(model_class):
        q = MagicMock()
        f = MagicMock()
        q.filter.return_value = f
        if model_class.__name__ == "Project":
            f.first.return_value = mock_project
        else:  # Document quota check
            f.count.return_value = 0
        return q

    mock_db.query.side_effect = _query_side_effect

    pdf_bytes = create_valid_pdf_bytes("Pin 1: VCC 3.3V, Pin 2: GND")

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_storage_service] = lambda: mock_storage

    client = TestClient(app)
    try:
        response = client.post(
            f"/v1/projects/{mock_project.id}/documents/upload",
            files={"file": ("datasheet.pdf", pdf_bytes, "application/pdf")},
            data={"version": "v1.2"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "datasheet.pdf"
        assert data["version"] == "v1.2"
        assert data["extraction_status"] == "ready"
        assert data["page_count"] == 1
        assert data["download_url"] == "https://example.com/download/doc.pdf"
        assert mock_storage.upload_file.called
        assert mock_db.add.called
        assert mock_db.commit.called
    finally:
        app.dependency_overrides.clear()


def test_upload_invalid_file_extension(mock_user: User, mock_project: Project) -> None:
    """Uploading a non-PDF file returns 400 Bad Request."""
    mock_db = MagicMock()
    mock_storage = MagicMock()

    def _query_side_effect(model_class):
        q = MagicMock()
        f = MagicMock()
        q.filter.return_value = f
        if model_class.__name__ == "Project":
            f.first.return_value = mock_project
        else:
            f.count.return_value = 0
        return q

    mock_db.query.side_effect = _query_side_effect

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_storage_service] = lambda: mock_storage

    client = TestClient(app)
    try:
        response = client.post(
            f"/v1/projects/{mock_project.id}/documents/upload",
            files={"file": ("firmware.c", b"int main() {}", "text/plain")},
        )
        assert response.status_code == 400
        assert "Only '.pdf' documents are supported" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_upload_oversized_file(mock_user: User, mock_project: Project) -> None:
    """Uploading a PDF exceeding maximum upload size returns 413 Payload Too Large."""
    mock_db = MagicMock()
    mock_storage = MagicMock()

    def _query_side_effect(model_class):
        q = MagicMock()
        f = MagicMock()
        q.filter.return_value = f
        if model_class.__name__ == "Project":
            f.first.return_value = mock_project
        else:
            f.count.return_value = 0
        return q

    mock_db.query.side_effect = _query_side_effect

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_storage_service] = lambda: mock_storage

    # Create dummy bytes > 10MB default
    oversized_bytes = b"%PDF-1.4 " + (b"A" * (11 * 1024 * 1024))

    client = TestClient(app)
    try:
        response = client.post(
            f"/v1/projects/{mock_project.id}/documents/upload",
            files={"file": ("huge_datasheet.pdf", oversized_bytes, "application/pdf")},
        )
        assert response.status_code == 413
        assert "exceeds maximum allowed size" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_upload_malformed_pdf_sets_failed_status(mock_user: User, mock_project: Project) -> None:
    """Uploading a corrupt PDF still stores metadata and records failed extraction status."""
    mock_db = MagicMock()
    mock_storage = MagicMock()

    def _query_side_effect(model_class):
        q = MagicMock()
        f = MagicMock()
        q.filter.return_value = f
        if model_class.__name__ == "Project":
            f.first.return_value = mock_project
        else:
            f.count.return_value = 0
        return q

    mock_db.query.side_effect = _query_side_effect

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_storage_service] = lambda: mock_storage

    client = TestClient(app)
    try:
        response = client.post(
            f"/v1/projects/{mock_project.id}/documents/upload",
            files={"file": ("corrupt.pdf", b"%PDF-1.4 corrupt junk data", "application/pdf")},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "corrupt.pdf"
        assert data["extraction_status"] == "failed"
        assert data["error_message"] is not None
        assert mock_storage.upload_file.called
    finally:
        app.dependency_overrides.clear()


def test_list_project_documents(mock_user: User, mock_project: Project) -> None:
    """Listing documents returns metadata for all documents in the project."""
    mock_db = MagicMock()
    mock_storage = MagicMock()
    mock_storage.get_download_url.return_value = "https://example.com/doc.pdf"

    doc1 = Document(
        id=uuid.uuid4(),
        project_id=mock_project.id,
        filename="doc1.pdf",
        version="v1",
        size_bytes=1024,
        checksum="hash1",
        storage_key="key1",
        extraction_status="ready",
        page_count=5,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_db.query.return_value.filter.return_value.first.return_value = mock_project
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [doc1]

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_storage_service] = lambda: mock_storage

    client = TestClient(app)
    try:
        response = client.get(f"/v1/projects/{mock_project.id}/documents")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["filename"] == "doc1.pdf"
        assert data[0]["extraction_status"] == "ready"
        assert data[0]["page_count"] == 5
    finally:
        app.dependency_overrides.clear()


def test_get_project_document_detail(mock_user: User, mock_project: Project) -> None:
    """Retrieving a single document includes extracted text and text length."""
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        project_id=mock_project.id,
        filename="datasheet.pdf",
        version="1.0",
        size_bytes=2048,
        checksum="hash",
        storage_key="key",
        extraction_status="ready",
        page_count=3,
        extracted_text="Chapter 1: Power Management Features",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_db = MagicMock()
    mock_storage = MagicMock()
    mock_db.query.return_value.filter.return_value.first.side_effect = [mock_project, doc]

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_storage_service] = lambda: mock_storage

    client = TestClient(app)
    try:
        response = client.get(f"/v1/projects/{mock_project.id}/documents/{doc_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "datasheet.pdf"
        assert data["extracted_text"] == "Chapter 1: Power Management Features"
        assert data["text_length"] == len("Chapter 1: Power Management Features")
    finally:
        app.dependency_overrides.clear()


def test_delete_project_document(mock_user: User, mock_project: Project) -> None:
    """Deleting a document deletes it from storage and database."""
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        project_id=mock_project.id,
        filename="datasheet.pdf",
        size_bytes=100,
        checksum="hash",
        storage_key=f"projects/{mock_project.id}/documents/{doc_id}_datasheet.pdf",
        extraction_status="ready",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_db = MagicMock()
    mock_storage = MagicMock()
    mock_db.query.return_value.filter.return_value.first.side_effect = [mock_project, doc]

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_storage_service] = lambda: mock_storage

    client = TestClient(app)
    try:
        response = client.delete(f"/v1/projects/{mock_project.id}/documents/{doc_id}")
        assert response.status_code == 204
        assert mock_storage.delete_file.called
        assert mock_db.delete.called
        assert mock_db.commit.called
    finally:
        app.dependency_overrides.clear()


def test_document_project_isolation(mock_user: User, other_user: User) -> None:
    """Accessing documents belonging to another user's project returns 404."""
    mock_db = MagicMock()
    mock_storage = MagicMock()
    # Project lookup for current_user returns None
    mock_db.query.return_value.filter.return_value.first.return_value = None

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_storage_service] = lambda: mock_storage

    client = TestClient(app)
    other_project_id = uuid.uuid4()
    try:
        response = client.get(f"/v1/projects/{other_project_id}/documents")
        assert response.status_code == 404
        assert "Project not found" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
