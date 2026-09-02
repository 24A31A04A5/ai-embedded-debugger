"""Tests for Phase 4.3 — Serial Log Analysis for the AI Embedded Debugger.

Covers:
1. Normal UART/serial log analysis
2. Runtime error detection
3. Crash/fault detection (ESP32 Guru Meditation / ARM HardFault)
4. Repeated-error detection
5. Warning classification
6. Timeout / communication failure
7. Correlation with existing code/compiler context
8. Clean / no-log handling
9. Preservation of grounded datasheet context
10. Existing debug behavior
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.ai.gemini import SYSTEM_INSTRUCTION, analyze_debugging_context
from app.core.auth import get_current_user
from app.core.database import get_db
from app.main import app
from app.models.project import Project
from app.models.user import User
from app.schemas.context import (
    AssembledDebugContext,
    DocumentContext,
    ProjectContext,
)
from app.schemas.debug import (
    CodeIssue,
    CompilerMessage,
    DebugResponse,
    DocumentCitation,
    LikelyCause,
    SerialLogEvent,
)


# ─────────────────────────────────────────────
# Shared test fixtures
# ─────────────────────────────────────────────


@pytest.fixture
def mock_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="serial_eng@example.com",
        clerk_id="user_clerk_serial",
        auth_provider="clerk",
        plan="free",
    )


@pytest.fixture
def mock_project(mock_user: User) -> Project:
    return Project(
        id=uuid.uuid4(),
        owner_id=mock_user.id,
        name="ESP32 Serial Debug Project",
        description="Phase 4.3 serial analysis test bed",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _fake_gemini_client(response_obj: DebugResponse) -> MagicMock:
    """Return a mock genai.Client whose generate_content produces response_obj."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = response_obj.model_dump_json()
    mock_client.models.generate_content.return_value = mock_resp
    return mock_client


# ─────────────────────────────────────────────
# Sample response fixtures
# ─────────────────────────────────────────────

NORMAL_LOG_RESPONSE = DebugResponse(
    problem_observed="System booted successfully; WiFi connection timed out during DHCP negotiation.",
    evidence_used=[
        "[00:00:01.200] I (320) wifi: Connected to AP 'Office_IoT'",
        "[00:00:06.500] E (5620) wifi: DHCP client timeout, failed to obtain IP",
    ],
    likely_causes=[
        LikelyCause(
            cause="DHCP server not responding or AP has exhausted available IP address pool",
            plausibility="high",
        )
    ],
    recommended_steps=[
        "Verify DHCP server connectivity and IP pool availability on the router.",
        "Test with a static IP configuration to isolate DHCP protocol failure.",
    ],
    proposed_fix="Configure a fallback static IP or increase the DHCP timeout in esp_netif.",
    corrected_code=None,
    risks_limitations=None,
    follow_up_required=None,
    serial_log_events=[
        SerialLogEvent(
            event_type="timeout",
            severity="high",
            is_repeated=False,
            timestamp="00:00:06.500",
            message="DHCP client timeout, failed to obtain IP",
            evidence="[00:00:06.500] E (5620) wifi: DHCP client timeout, failed to obtain IP",
            likely_cause="DHCP server unreachable or pool exhausted.",
            suggested_action="Configure static IP address fallback in WiFi network interface.",
        )
    ],
)

CRASH_FAULT_RESPONSE = DebugResponse(
    problem_observed="Fatal crash: ESP32 Guru Meditation Error (LoadProhibited) caused by NULL pointer dereference in process_packet() at PC 0x400d1234.",
    evidence_used=[
        "Guru Meditation Error: Core 0 panic'ed (LoadProhibited). Exception was unhandled.",
        "Core 0 register dump:",
        "PC : 0x400d1234 PS : 0x00060030 A0 : 0x800d1567 A1 : 0x3ffb12a0",
        "A2 : 0x00000000 A3 : 0x3ffb4000",
        "Backtrace: 0x400d1234:0x3ffb12a0 0x400d1567:0x3ffb12c0",
    ],
    likely_causes=[
        LikelyCause(
            cause="A2 register is 0x00000000; process_packet attempted to load from address 0x0 (NULL dereference)",
            plausibility="high",
        )
    ],
    recommended_steps=[
        "Inspect process_packet() to ensure packet pointer passed in A2 is validated before dereferencing.",
        "Add an assert or check: if (packet == NULL) return ESP_ERR_INVALID_ARG;",
    ],
    proposed_fix="Validate incoming packet buffer pointer before accessing structure fields.",
    corrected_code="if (packet == NULL) {\n    ESP_LOGE(TAG, \"packet is NULL\");\n    return ESP_ERR_INVALID_ARG;\n}",
    risks_limitations=None,
    follow_up_required=None,
    code_issues=[
        CodeIssue(
            kind="null_pointer",
            severity="critical",
            confirmed=True,
            description="Dereferencing pointer in A2 which is 0x00000000 (NULL pointer).",
            location="process_packet()",
            evidence="A2 : 0x00000000; LoadProhibited exception",
            suggestion="Add NULL check before field access.",
        )
    ],
    serial_log_events=[
        SerialLogEvent(
            event_type="panic",
            severity="critical",
            is_repeated=False,
            timestamp=None,
            message="Guru Meditation Error: Core 0 panic'ed (LoadProhibited)",
            evidence="Guru Meditation Error: Core 0 panic'ed (LoadProhibited). Exception was unhandled.\nPC : 0x400d1234  A2 : 0x00000000",
            likely_cause="Load from invalid/NULL memory address (A2=0x00000000).",
            suggested_action="Use addr2line -e build/app.elf 0x400d1234 to locate the exact source line.",
        )
    ],
)

REPEATED_ERROR_RESPONSE = DebugResponse(
    problem_observed="I2C sensor communication failure repeating continuously (4 times) due to I2C ACK timeout.",
    evidence_used=[
        "[10.102s] E (10102) bme280: i2c_master_write returned ESP_ERR_TIMEOUT",
        "[11.102s] E (11102) bme280: i2c_master_write returned ESP_ERR_TIMEOUT",
        "[12.102s] E (12102) bme280: i2c_master_write returned ESP_ERR_TIMEOUT",
        "[13.102s] E (13102) bme280: i2c_master_write returned ESP_ERR_TIMEOUT",
    ],
    likely_causes=[
        LikelyCause(
            cause="BME280 sensor not connected, incorrect I2C address (0x76 vs 0x77), or missing pull-up resistors on SDA/SCL",
            plausibility="high",
        )
    ],
    recommended_steps=[
        "Run an I2C bus scanner to verify the target device responds at the expected address.",
        "Check 3.3V power, GND, and 4.7kΩ pull-up resistors on SDA/SCL.",
    ],
    proposed_fix="Verify hardware wiring and verify SDO pin state for correct I2C address selection.",
    corrected_code=None,
    risks_limitations=None,
    follow_up_required=None,
    serial_log_events=[
        SerialLogEvent(
            event_type="repeated_error",
            severity="high",
            is_repeated=True,
            repeat_count=4,
            timestamp="10.102s - 13.102s",
            message="i2c_master_write returned ESP_ERR_TIMEOUT",
            evidence="[10.102s] E (10102) bme280: i2c_master_write returned ESP_ERR_TIMEOUT (repeated 4x)",
            likely_cause="Sensor unresponsive on I2C bus; missing pull-up or incorrect address.",
            suggested_action="Check I2C bus with logic analyzer and verify sensor address.",
        )
    ],
)

WARNING_LOG_RESPONSE = DebugResponse(
    problem_observed="System running in degraded mode: high heap fragmentation warning logged by memory manager.",
    evidence_used=[
        "[00:05:22] W (322000) heap_caps: Free 8-bit memory is low (1240 bytes left, lowest: 512 bytes)",
    ],
    likely_causes=[
        LikelyCause(
            cause="Dynamic memory allocation (malloc/free) fragmentation over long runtime",
            plausibility="medium",
        )
    ],
    recommended_steps=[
        "Use static allocation or memory pools for recurring packet buffers.",
        "Profile heap usage using heap_caps_get_free_size(MALLOC_CAP_8BIT).",
    ],
    proposed_fix="Replace repeated malloc in packet handler with a static ring buffer.",
    corrected_code=None,
    risks_limitations=None,
    follow_up_required=None,
    serial_log_events=[
        SerialLogEvent(
            event_type="warning",
            severity="medium",
            is_repeated=False,
            timestamp="00:05:22",
            message="Free 8-bit memory is low (1240 bytes left)",
            evidence="[00:05:22] W (322000) heap_caps: Free 8-bit memory is low (1240 bytes left, lowest: 512 bytes)",
            likely_cause="Heap fragmentation from repeated dynamic buffer allocations.",
            suggested_action="Refactor dynamic allocation to static memory pools.",
        )
    ],
)

GROUNDED_LOG_RESPONSE = DebugResponse(
    problem_observed="I2C sensor read failed with NACK; datasheet states sensor address is 0x68 (when AD0=GND) or 0x69 (when AD0=VCC).",
    evidence_used=[
        "[00:01:05.120] E (65120) mpu6050: I2C transmission failed with NACK at addr 0x68",
        "MPU-6050 Datasheet (p.15): The I2C address is 0x68 if the AD0 pin is connected to GND, or 0x69 if connected to VCC.",
    ],
    likely_causes=[
        LikelyCause(
            cause="AD0 pin on sensor breakout is pulled HIGH to VCC, making the device address 0x69 instead of 0x68",
            plausibility="high",
        )
    ],
    recommended_steps=[
        "Change I2C slave address in code from 0x68 to 0x69, or pull AD0 pin to GND.",
    ],
    proposed_fix="Update sensor address define to 0x69.",
    corrected_code="#define MPU6050_I2C_ADDR 0x69",
    risks_limitations=None,
    follow_up_required=None,
    datasheet_citations=[
        DocumentCitation(
            chunk_id=str(uuid.uuid4()),
            document_id=str(uuid.uuid4()),
            document_name="mpu6050_datasheet.pdf",
            page_number=15,
            relevant_snippet="The slave address of the MPU-6050 is b110100X which is 7 bits long. The LSB bit of the 7-bit address is determined by the logic level on pin AD0.",
            relevance_explanation="Explains why 0x68 fails if AD0 is tied HIGH.",
        )
    ],
    grounded_summary="MPU-6050 7-bit I2C address is 0x68 (AD0=0) or 0x69 (AD0=1).",
    serial_log_events=[
        SerialLogEvent(
            event_type="communication_error",
            severity="high",
            is_repeated=False,
            timestamp="00:01:05.120",
            message="I2C transmission failed with NACK at addr 0x68",
            evidence="[00:01:05.120] E (65120) mpu6050: I2C transmission failed with NACK at addr 0x68",
            likely_cause="Device did not acknowledge address 0x68 (AD0 pin may be pulled HIGH to VCC).",
            suggested_action="Try I2C address 0x69 or check AD0 pin wiring.",
        )
    ],
)


# ─────────────────────────────────────────────
# 1. Normal UART/serial log analysis
# ─────────────────────────────────────────────


class TestNormalSerialLogAnalysis:
    def test_serial_logs_parsed_into_serial_log_events(self) -> None:
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="WiFi Logger"),
            serial_logs="[00:00:01.200] I (320) wifi: Connected to AP\n[00:00:06.500] E (5620) wifi: DHCP client timeout, failed to obtain IP",
        )
        mock_client = _fake_gemini_client(NORMAL_LOG_RESPONSE)
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            result = analyze_debugging_context(ctx)

        assert result.serial_log_events is not None
        assert len(result.serial_log_events) == 1
        ev = result.serial_log_events[0]
        assert ev.event_type == "timeout"
        assert ev.severity == "high"
        assert ev.timestamp == "00:00:06.500"
        assert "DHCP client timeout" in ev.message
        assert ev.suggested_action is not None

    def test_system_instruction_contains_serial_log_section(self) -> None:
        assert "serial_log_events" in SYSTEM_INSTRUCTION
        assert "crash_fault" in SYSTEM_INSTRUCTION
        assert "watchdog_reset" in SYSTEM_INSTRUCTION
        assert "brownout_reset" in SYSTEM_INSTRUCTION
        assert "repeated_error" in SYSTEM_INSTRUCTION


# ─────────────────────────────────────────────
# 2. Runtime error detection
# ─────────────────────────────────────────────


class TestRuntimeErrorDetection:
    def test_runtime_error_event_schema_and_classification(self) -> None:
        ev = SerialLogEvent(
            event_type="runtime_error",
            severity="high",
            is_repeated=False,
            timestamp="12.450s",
            message="bme280_init failed: returned error -1",
            evidence="[12.450s] E: bme280_init failed: returned error -1",
            likely_cause="I2C peripheral not initialized or sensor not responding.",
            suggested_action="Check I2C bus initialization return value.",
        )
        assert ev.event_type == "runtime_error"
        assert ev.severity == "high"
        assert ev.is_repeated is False
        assert ev.timestamp == "12.450s"


# ─────────────────────────────────────────────
# 3. Crash / fault detection (ESP32 Guru Meditation / ARM HardFault)
# ─────────────────────────────────────────────


class TestCrashFaultDetection:
    def test_guru_meditation_panic_detected_with_register_dump(self) -> None:
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="ESP32 Panic"),
            serial_logs=(
                "Guru Meditation Error: Core 0 panic'ed (LoadProhibited). Exception was unhandled.\n"
                "Core 0 register dump:\n"
                "PC : 0x400d1234 PS : 0x00060030 A0 : 0x800d1567 A1 : 0x3ffb12a0\n"
                "A2 : 0x00000000 A3 : 0x3ffb4000\n"
            ),
        )
        mock_client = _fake_gemini_client(CRASH_FAULT_RESPONSE)
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            result = analyze_debugging_context(ctx)

        assert result.serial_log_events is not None
        assert len(result.serial_log_events) >= 1
        panic_ev = result.serial_log_events[0]
        assert panic_ev.event_type == "panic"
        assert panic_ev.severity == "critical"
        assert "LoadProhibited" in panic_ev.message
        assert "A2=0x00000000" in panic_ev.likely_cause or "NULL" in panic_ev.likely_cause


# ─────────────────────────────────────────────
# 4. Repeated-error detection
# ─────────────────────────────────────────────


class TestRepeatedErrorDetection:
    def test_repeated_i2c_timeout_flagged_with_repeat_count(self) -> None:
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="I2C Loop"),
            serial_logs=(
                "[10.102s] E (10102) bme280: i2c_master_write returned ESP_ERR_TIMEOUT\n"
                "[11.102s] E (11102) bme280: i2c_master_write returned ESP_ERR_TIMEOUT\n"
                "[12.102s] E (12102) bme280: i2c_master_write returned ESP_ERR_TIMEOUT\n"
                "[13.102s] E (13102) bme280: i2c_master_write returned ESP_ERR_TIMEOUT\n"
            ),
        )
        mock_client = _fake_gemini_client(REPEATED_ERROR_RESPONSE)
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            result = analyze_debugging_context(ctx)

        assert result.serial_log_events is not None
        rep_ev = result.serial_log_events[0]
        assert rep_ev.is_repeated is True
        assert rep_ev.repeat_count == 4
        assert rep_ev.event_type == "repeated_error"


# ─────────────────────────────────────────────
# 5. Warning classification
# ─────────────────────────────────────────────


class TestWarningClassification:
    def test_heap_memory_warning_classified_medium_severity(self) -> None:
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="Heap Watcher"),
            serial_logs="[00:05:22] W (322000) heap_caps: Free 8-bit memory is low (1240 bytes left, lowest: 512 bytes)",
        )
        mock_client = _fake_gemini_client(WARNING_LOG_RESPONSE)
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            result = analyze_debugging_context(ctx)

        assert result.serial_log_events is not None
        warn_ev = result.serial_log_events[0]
        assert warn_ev.event_type == "warning"
        assert warn_ev.severity == "medium"
        assert warn_ev.is_repeated is False


# ─────────────────────────────────────────────
# 6. Timeout / communication failure
# ─────────────────────────────────────────────


class TestTimeoutCommunicationFailure:
    def test_communication_error_event_schema(self) -> None:
        ev = SerialLogEvent(
            event_type="communication_error",
            severity="high",
            message="UART framing error on USART2",
            evidence="[0.450] USART2: Framing error detected (FE flag set)",
            likely_cause="Baud rate mismatch (115200 configured vs 9600 transmitted) or noisy RX line.",
            suggested_action="Verify baud rate, parity, and stop bit configuration on both ends.",
        )
        assert ev.event_type == "communication_error"
        assert ev.severity == "high"
        assert ev.likely_cause is not None
        assert "Baud rate" in ev.likely_cause


# ─────────────────────────────────────────────
# 7. Correlation with existing code / compiler context
# ─────────────────────────────────────────────


class TestCorrelationWithCodeAndCompiler:
    def test_crash_correlates_with_null_pointer_code_issue(self) -> None:
        """When a crash occurs, serial_log_events and code_issues both capture the root cause."""
        result = CRASH_FAULT_RESPONSE
        assert result.serial_log_events is not None
        assert result.code_issues is not None
        assert len(result.serial_log_events) >= 1
        assert len(result.code_issues) >= 1

        # Code issue is confirmed because of the crash register dump
        code_issue = result.code_issues[0]
        assert code_issue.kind == "null_pointer"
        assert code_issue.confirmed is True

        # Serial event is a panic
        log_event = result.serial_log_events[0]
        assert log_event.event_type == "panic"


# ─────────────────────────────────────────────
# 8. Clean / no-log handling
# ─────────────────────────────────────────────


class TestCleanNoLogHandling:
    def test_no_serial_log_events_when_logs_empty(self) -> None:
        clean_resp = DebugResponse(
            problem_observed="No runtime log issues present.",
            evidence_used=["No serial logs submitted."],
            likely_causes=[LikelyCause(cause="Build issue or code logic bug", plausibility="medium")],
            recommended_steps=["Upload serial logs if available."],
            proposed_fix="Review code logic.",
            serial_log_events=None,
        )
        ctx = AssembledDebugContext(
            project=ProjectContext(project_id=uuid.uuid4(), project_name="No Logs Project"),
            firmware_code="void setup() {}",
            serial_logs="",
        )
        mock_client = _fake_gemini_client(clean_resp)
        with patch("app.ai.gemini.genai.Client", return_value=mock_client):
            result = analyze_debugging_context(ctx)

        assert result.serial_log_events is None

    def test_system_instruction_forbids_fabricating_log_events(self) -> None:
        assert "Do NOT invent log events" in SYSTEM_INSTRUCTION
        assert "set serial_log_events = None" in SYSTEM_INSTRUCTION


# ─────────────────────────────────────────────
# 9. Preservation of grounded datasheet context
# ─────────────────────────────────────────────


class TestGroundedDatasheetPreservation:
    def test_datasheet_citations_coexist_with_serial_log_events(self) -> None:
        result = GROUNDED_LOG_RESPONSE
        assert result.datasheet_citations is not None
        assert len(result.datasheet_citations) == 1
        assert "mpu6050_datasheet.pdf" in result.datasheet_citations[0].document_name
        assert result.grounded_summary is not None
        assert result.serial_log_events is not None
        assert len(result.serial_log_events) == 1
        assert result.serial_log_events[0].event_type == "communication_error"


# ─────────────────────────────────────────────
# 10. Existing debug behavior
# ─────────────────────────────────────────────


class TestExistingDebugBehavior:
    def test_debug_endpoint_returns_serial_log_events_in_response(
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
            return_value=NORMAL_LOG_RESPONSE,
        ):
            client = TestClient(app)
            try:
                response = client.post(
                    f"/v1/projects/{mock_project.id}/debug",
                    json={
                        "serial_logs": "[00:00:06.500] E (5620) wifi: DHCP client timeout, failed to obtain IP",
                    },
                )
                assert response.status_code == 200
                data = response.json()
                assert data["problem_observed"] == NORMAL_LOG_RESPONSE.problem_observed
                assert data["serial_log_events"] is not None
                assert len(data["serial_log_events"]) == 1
                ev = data["serial_log_events"][0]
                assert ev["event_type"] == "timeout"
                assert ev["severity"] == "high"
                assert ev["timestamp"] == "00:00:06.500"
                assert "DHCP" in ev["message"]
            finally:
                app.dependency_overrides.clear()

    def test_legacy_debug_response_without_serial_log_events_valid(self) -> None:
        """Older payloads without serial_log_events remain valid (field defaults to None)."""
        resp = DebugResponse(
            problem_observed="I2C pull-up missing.",
            evidence_used=["Log shows timeout."],
            likely_causes=[LikelyCause(cause="Missing resistor", plausibility="high")],
            recommended_steps=["Add 4.7k resistor."],
            proposed_fix="Attach pull-ups.",
        )
        assert resp.serial_log_events is None
        assert resp.compiler_messages is None
        assert resp.code_issues is None
