"""Tests for Phase 3.4 — Grounded Gemini Answers with Document Context."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.ai.gemini import analyze_debugging_context
from app.core.auth import get_current_user
from app.core.database import get_db
from app.main import app
from app.models.debug_message import DebugMessage
from app.models.debug_session import DebugSession
from app.models.document_chunk import DocumentChunk
from app.models.project import Project
from app.models.user import User
from app.schemas.context import (
    AssembledDebugContext,
    DocumentContext,
    ProjectContext,
)
from app.schemas.debug import DebugRequest, DebugResponse, DocumentCitation, LikelyCause
from app.schemas.document import DocumentSearchResultItem
from app.services.context_assembly import ContextAssemblyService
from app.services.retrieval import DocumentRetrievalService
from app.services.storage import BaseStorageService, get_storage_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="embedded_dev@example.com",
        clerk_id="user_clerk_grounded",
        auth_provider="clerk",
        plan="free",
    )


@pytest.fixture
def other_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="intruder@example.com",
        clerk_id="user_clerk_intruder",
        auth_provider="clerk",
        plan="free",
    )


@pytest.fixture
def mock_project(mock_user: User) -> Project:
    return Project(
        id=uuid.uuid4(),
        owner_id=mock_user.id,
        name="ESP32 Grounded Project",
        description="Datasheet Grounded RAG Workspace",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def other_project(other_user: User) -> Project:
    return Project(
        id=uuid.uuid4(),
        owner_id=other_user.id,
        name="Secret STM32 Project",
        description="Private Workspace",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


MOCK_GROUNDED_RESPONSE = DebugResponse(
    problem_observed="I2C pull-up resistor missing for ESP32 GPIO21/22",
    evidence_used=[
        "ESP32 Technical Reference Manual (p.45): GPIO21/22 do not have internal pull-ups enabled by default in open-drain mode",
        "Serial log: ESP_ERR_TIMEOUT on i2c_master_write",
    ],
    likely_causes=[
        LikelyCause(
            cause="Missing external 4.7kΩ pull-up resistors on SDA (GPIO21) and SCL (GPIO22)",
            plausibility="high",
        )
    ],
    recommended_steps=[
        "Connect 4.7kΩ pull-up resistors to 3.3V on SDA and SCL lines",
        "Verify bus voltage with oscilloscope or multimeter",
    ],
    proposed_fix="Add external pull-ups or enable internal weak pull-ups in code (gpio_pullup_en).",
    corrected_code="gpio_pullup_en(GPIO_NUM_21);\ngpio_pullup_en(GPIO_NUM_22);",
    risks_limitations="Internal pull-ups (~45kΩ) may be too weak for high-speed I2C modes (>100kHz).",
    follow_up_required=None,
    datasheet_citations=[
        DocumentCitation(
            chunk_id=str(uuid.uuid4()),
            document_id=str(uuid.uuid4()),
            document_name="esp32_technical_reference.pdf",
            page_number=45,
            relevant_snippet="GPIO21 and GPIO22 require external pull-up resistors for reliable I2C communication at standard bus speeds.",
            relevance_explanation="Explains why I2C master write times out without pull-up resistance.",
        )
    ],
    grounded_summary="ESP32 I2C pins require pull-up resistors (typically 4.7kΩ to 3.3V) for open-drain bus operation.",
)


# ---------------------------------------------------------------------------
# Unit tests: Context Assembly with Vector Retrieval
# ---------------------------------------------------------------------------


class TestGroundedContextAssembly:
    """Tests that vector retrieval integrates cleanly into context assembly."""

    def test_retrieved_chunks_included_in_assembled_context(
        self,
        mock_user: User,
        mock_project: Project,
    ) -> None:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        mock_retrieval = MagicMock(spec=DocumentRetrievalService)
        chunk_uuid = uuid.uuid4()
        doc_uuid = uuid.uuid4()
        mock_retrieval.search.return_value = [
            DocumentSearchResultItem(
                chunk_id=chunk_uuid,
                document_id=doc_uuid,
                document_name="esp32_datasheet.pdf",
                content="GPIO21 is SDA, GPIO22 is SCL with 3.3V logic level.",
                page_number=12,
                chunk_index=1,
                similarity_score=0.91,
                metadata_json={"section": "Pinout"},
            )
        ]

        svc = ContextAssemblyService(db=mock_db)
        context = svc.assemble_context(
            project_id=mock_project.id,
            current_user=mock_user,
            user_question="What are the I2C pins on ESP32?",
            retrieval_service=mock_retrieval,
        )

        assert len(context.document_context) == 1
        doc = context.document_context[0]
        assert doc.chunk_id == str(chunk_uuid)
        assert doc.doc_id == str(doc_uuid)
        assert doc.title == "esp32_datasheet.pdf"
        assert doc.page_number == 12
        assert doc.score == 0.91

        # Check formatted prompt contains the document chunk with attributes
        formatted = context.format_prompt()
        assert "<retrieved_datasheets_and_documents>" in formatted
        assert f'chunk_id="{chunk_uuid}"' in formatted
        assert 'document="esp32_datasheet.pdf"' in formatted
        assert 'page="12"' in formatted
        assert "GPIO21 is SDA, GPIO22 is SCL" in formatted

    def test_no_results_retrieval_handled_gracefully(
        self,
        mock_user: User,
        mock_project: Project,
    ) -> None:
        """When vector retrieval returns 0 chunks, context assembly completes normally."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        mock_retrieval = MagicMock(spec=DocumentRetrievalService)
        mock_retrieval.search.return_value = []

        svc = ContextAssemblyService(db=mock_db)
        context = svc.assemble_context(
            project_id=mock_project.id,
            current_user=mock_user,
            user_question="Unrelated query without matches",
            retrieval_service=mock_retrieval,
        )

        assert context.document_context == []
        formatted = context.format_prompt()
        assert "<retrieved_datasheets_and_documents>" not in formatted

    def test_retrieval_exception_does_not_block_context_assembly(
        self,
        mock_user: User,
        mock_project: Project,
    ) -> None:
        """If vector search errors (e.g. embedding API down), assembly still succeeds."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        mock_retrieval = MagicMock(spec=DocumentRetrievalService)
        mock_retrieval.search.side_effect = RuntimeError("Embedding service unavailable")

        svc = ContextAssemblyService(db=mock_db)
        context = svc.assemble_context(
            project_id=mock_project.id,
            current_user=mock_user,
            firmware_code="void setup() { Wire.begin(); }",
            retrieval_service=mock_retrieval,
        )

        assert context.document_context == []
        assert "Wire.begin()" in context.firmware_code

    def test_selected_document_ids_passed_to_retrieval(
        self,
        mock_user: User,
        mock_project: Project,
    ) -> None:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        mock_retrieval = MagicMock(spec=DocumentRetrievalService)
        mock_retrieval.search.return_value = []

        selected_doc = uuid.uuid4()
        svc = ContextAssemblyService(db=mock_db)
        svc.assemble_context(
            project_id=mock_project.id,
            current_user=mock_user,
            user_question="Check timing constraints",
            selected_document_ids=[selected_doc],
            retrieval_service=mock_retrieval,
        )

        mock_retrieval.search.assert_called_once_with(
            project_id=mock_project.id,
            query="Check timing constraints",
            top_k=5,
            similarity_threshold=0.0,
            document_ids=[selected_doc],
        )


# ---------------------------------------------------------------------------
# Unit tests: Gemini Analysis with Grounded Context
# ---------------------------------------------------------------------------


class TestGeminiGroundedAnalysis:
    """Tests for analyze_debugging_context handling of grounded context."""

    def test_analyze_debugging_context_calls_gemini_with_grounded_prompt(self) -> None:
        proj_ctx = ProjectContext(project_id=uuid.uuid4(), project_name="ESP32 Project")
        doc_ctx = DocumentContext(
            doc_id=str(uuid.uuid4()),
            title="stm32_ref.pdf",
            snippet="TIM2 is a 32-bit timer on APB1.",
            page_number=101,
            chunk_id=str(uuid.uuid4()),
        )
        context = AssembledDebugContext(
            project=proj_ctx,
            user_question="Is TIM2 16-bit or 32-bit?",
            document_context=[doc_ctx],
        )

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = MOCK_GROUNDED_RESPONSE.model_dump_json()
        mock_client.models.generate_content.return_value = mock_response

        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            diagnosis = analyze_debugging_context(context)

            assert diagnosis.problem_observed == MOCK_GROUNDED_RESPONSE.problem_observed
            assert diagnosis.datasheet_citations is not None
            assert len(diagnosis.datasheet_citations) == 1
            assert diagnosis.grounded_summary is not None

            # Verify prompt contained the retrieved document block
            call_kwargs = mock_client.models.generate_content.call_args[1]
            prompt = call_kwargs["contents"]
            assert "<retrieved_datasheets_and_documents>" in prompt
            assert "TIM2 is a 32-bit timer" in prompt

    def test_analyze_debugging_context_handles_empty_response(self) -> None:
        context = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="P"),
        )
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = ""
        mock_client.models.generate_content.return_value = mock_response

        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            with pytest.raises(ValueError, match="Empty response"):
                analyze_debugging_context(context)


# ---------------------------------------------------------------------------
# API Endpoint Integration Tests: /projects/{project_id}/debug & /sessions
# ---------------------------------------------------------------------------


class TestGroundedDebugEndpoints:
    """Integration tests for debug and session endpoints with vector retrieval."""

    def test_debug_endpoint_executes_grounded_analysis(
        self,
        mock_user: User,
        mock_project: Project,
    ) -> None:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        with patch(
            "app.routers.debug.analyze_debugging_context",
            return_value=MOCK_GROUNDED_RESPONSE,
        ) as mock_ai:
            client = TestClient(app)
            try:
                response = client.post(
                    f"/v1/projects/{mock_project.id}/debug",
                    json={
                        "user_question": "Why is I2C timing out?",
                        "firmware_code": "Wire.begin(21, 22);",
                        "serial_logs": "[ERROR] I2C timeout",
                    },
                )
                assert response.status_code == 200
                data = response.json()
                assert data["problem_observed"] == MOCK_GROUNDED_RESPONSE.problem_observed
                assert data["datasheet_citations"] is not None
                assert len(data["datasheet_citations"]) == 1
                assert "esp32_technical_reference.pdf" in data["datasheet_citations"][0]["document_name"]
                assert data["grounded_summary"] is not None
                assert mock_ai.called
            finally:
                app.dependency_overrides.clear()

    def test_create_session_persists_grounded_response_and_metadata(
        self,
        mock_user: User,
        mock_project: Project,
    ) -> None:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        def fake_refresh(obj: object) -> None:
            if isinstance(obj, DebugSession):
                obj.created_at = datetime.now(UTC)
                obj.updated_at = datetime.now(UTC)
                obj.messages = []  # type: ignore[attr-defined]

        mock_db.refresh.side_effect = fake_refresh

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        with patch(
            "app.routers.sessions.analyze_debugging_context",
            return_value=MOCK_GROUNDED_RESPONSE,
        ):
            client = TestClient(app)
            try:
                response = client.post(
                    f"/v1/projects/{mock_project.id}/sessions",
                    json={
                        "title": "I2C Bus Debugging",
                        "user_question": "Why does I2C fail?",
                        "firmware_code": "Wire.begin();",
                    },
                )
                assert response.status_code == 201
                data = response.json()
                assert data["title"] == "I2C Bus Debugging"
                assert mock_db.add.called
                assert mock_db.commit.called
            finally:
                app.dependency_overrides.clear()

    def test_debug_endpoint_ownership_isolation(
        self,
        mock_user: User,
        other_project: Project,
    ) -> None:
        """User cannot trigger debug analysis on another user's project."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        client = TestClient(app)
        try:
            response = client.post(
                f"/v1/projects/{other_project.id}/debug",
                json={"user_question": "Diagnose unauthorized project"},
            )
            assert response.status_code == 404
            assert "Project not found" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_debug_endpoint_gemini_failure_sanitizes_errors(
        self,
        mock_user: User,
        mock_project: Project,
    ) -> None:
        """API key/secret leaks are prevented when Gemini fails."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        with patch(
            "app.routers.debug.analyze_debugging_context",
            side_effect=RuntimeError("Invalid api_key=SECRET_KEY_12345 provided"),
        ):
            client = TestClient(app)
            try:
                response = client.post(
                    f"/v1/projects/{mock_project.id}/debug",
                    json={"user_question": "Test query"},
                )
                assert response.status_code == 500
                detail = response.json()["detail"]
                assert "SECRET_KEY_12345" not in detail
                assert "AI Analysis failed" in detail
            finally:
                app.dependency_overrides.clear()
