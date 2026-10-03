"""In-process MockFabricateProvider (no network, no Domain DB)."""

from __future__ import annotations

import sqlite3
import tempfile
import uuid
from pathlib import Path
from typing import Any

from app.application.ports import ExternalCallStatus
from app.application.ports import FabricateCallResult
from app.infrastructure.mcp.fabricate_whitelist import FABRICATE_WHITELIST


class MockFabricateProvider:
    """Deterministic FabricateProvider for unit/integration tests."""

    def __init__(self) -> None:
        """Initialize in-memory conversation state."""
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._uploads: dict[str, bytes] = {}
        self._conversations: dict[str, dict[str, Any]] = {}
        self._poll_counts: dict[str, int] = {}
        self.fail_next_start = False

    def list_conversation_options(self) -> FabricateCallResult:
        """Return a fixed model list."""
        return self._ok(
            "list_conversation_options",
            {
                "models": [{"id": "mock-model", "name": "Mock"}],
                "modes": ["autonomous", "agent", "plan"],
                "approaches": ["dataset", "generator", "simulation"],
            },
        )

    def create_upload(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: str = "application/json",
    ) -> FabricateCallResult:
        """Store upload bytes under a generated id."""
        upload_id = f"upl_{uuid.uuid4().hex[:12]}"
        self._uploads[upload_id] = content
        return self._ok(
            "create_upload",
            {
                "upload_id": upload_id,
                "filename": filename,
                "content_type": content_type,
                "size": len(content),
            },
            args={"filename": filename, "size": len(content)},
        )

    def start_conversation(
        self,
        *,
        message: str,
        upload_ids: list[str],
        model: str | None = None,
        mode: str = "autonomous",
        approach: str = "dataset",
    ) -> FabricateCallResult:
        """Create a conversation that completes after one poll."""
        if self.fail_next_start:
            self.fail_next_start = False
            return FabricateCallResult(
                status=ExternalCallStatus.EXTERNAL_ERROR,
                tool="start_conversation",
                message="mock start failure",
            )
        conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
        self._conversations[conversation_id] = {
            "message": message,
            "upload_ids": list(upload_ids),
            "model": model or "mock-model",
            "mode": mode,
            "approach": approach,
            "status": "running",
            "stopped": False,
        }
        self._poll_counts[conversation_id] = 0
        return self._ok(
            "start_conversation",
            {"conversation_id": conversation_id, "status": "running"},
            args={
                "message": message,
                "upload_ids": upload_ids,
                "mode": mode,
                "approach": approach,
            },
        )

    def get_conversation_status(
        self,
        conversation_id: str,
    ) -> FabricateCallResult:
        """Return running once, then completed."""
        state = self._conversations.get(conversation_id)
        if state is None:
            return FabricateCallResult(
                status=ExternalCallStatus.VALIDATION_ERROR,
                tool="get_conversation_status",
                message="unknown conversation_id",
            )
        if state.get("stopped"):
            return self._ok(
                "get_conversation_status",
                {
                    "conversation_id": conversation_id,
                    "status": "cancelled",
                    "poll_after_ms": 0,
                },
                args={"conversation_id": conversation_id},
            )
        count = self._poll_counts.get(conversation_id, 0) + 1
        self._poll_counts[conversation_id] = count
        if count < 2:
            status = "running"
            poll = 10
        else:
            status = "completed"
            poll = 0
            state["status"] = "completed"
        return self._ok(
            "get_conversation_status",
            {
                "conversation_id": conversation_id,
                "status": status,
                "poll_after_ms": poll,
                "retryable": False,
            },
            args={"conversation_id": conversation_id},
        )

    def get_conversation_result(
        self,
        conversation_id: str,
    ) -> FabricateCallResult:
        """Return a downloadable SQLite file id."""
        if conversation_id not in self._conversations:
            return FabricateCallResult(
                status=ExternalCallStatus.VALIDATION_ERROR,
                tool="get_conversation_result",
                message="unknown conversation_id",
            )
        file_id = f"file_{conversation_id}"
        return self._ok(
            "get_conversation_result",
            {
                "conversation_id": conversation_id,
                "files": [
                    {
                        "file_id": file_id,
                        "filename": "equipment.sqlite",
                        "content_type": "application/x-sqlite3",
                    }
                ],
            },
            args={"conversation_id": conversation_id},
        )

    def download_conversation_file(
        self,
        *,
        conversation_id: str,
        file_id: str,
    ) -> FabricateCallResult:
        """Build a tiny valid staging SQLite and return its bytes."""
        if conversation_id not in self._conversations:
            return FabricateCallResult(
                status=ExternalCallStatus.VALIDATION_ERROR,
                tool="download_conversation_file",
                message="unknown conversation_id",
            )
        blob = _build_staging_sqlite()
        return self._ok(
            "download_conversation_file",
            {
                "conversation_id": conversation_id,
                "file_id": file_id,
                "bytes": blob,
                "filename": "equipment.sqlite",
            },
            args={
                "conversation_id": conversation_id,
                "file_id": file_id,
            },
        )

    def send_message(
        self,
        conversation_id: str,
        message: str,
        *,
        upload_ids: list[str] | None = None,
    ) -> FabricateCallResult:
        """Mark conversation running again for refine."""
        state = self._conversations.get(conversation_id)
        if state is None:
            return FabricateCallResult(
                status=ExternalCallStatus.VALIDATION_ERROR,
                tool="send_message",
                message="unknown conversation_id",
            )
        state["status"] = "running"
        state["stopped"] = False
        self._poll_counts[conversation_id] = 0
        return self._ok(
            "send_message",
            {"conversation_id": conversation_id, "status": "running"},
            args={
                "conversation_id": conversation_id,
                "message": message,
                "upload_ids": upload_ids or [],
            },
        )

    def stop_conversation(self, conversation_id: str) -> FabricateCallResult:
        """Cancel a conversation."""
        state = self._conversations.get(conversation_id)
        if state is None:
            return FabricateCallResult(
                status=ExternalCallStatus.VALIDATION_ERROR,
                tool="stop_conversation",
                message="unknown conversation_id",
            )
        state["stopped"] = True
        state["status"] = "cancelled"
        return self._ok(
            "stop_conversation",
            {"conversation_id": conversation_id, "status": "cancelled"},
            args={"conversation_id": conversation_id},
        )

    def retry_conversation(self, conversation_id: str) -> FabricateCallResult:
        """Retry by resetting poll counter."""
        state = self._conversations.get(conversation_id)
        if state is None:
            return FabricateCallResult(
                status=ExternalCallStatus.VALIDATION_ERROR,
                tool="retry_conversation",
                message="unknown conversation_id",
            )
        state["stopped"] = False
        state["status"] = "running"
        self._poll_counts[conversation_id] = 0
        return self._ok(
            "retry_conversation",
            {"conversation_id": conversation_id, "status": "running"},
            args={"conversation_id": conversation_id},
        )

    def _ok(
        self,
        tool: str,
        data: dict[str, Any],
        *,
        args: dict[str, Any] | None = None,
    ) -> FabricateCallResult:
        if tool not in FABRICATE_WHITELIST:
            return FabricateCallResult(
                status=ExternalCallStatus.FAILURE,
                tool=tool,
                message=f"tool {tool!r} is not whitelisted",
            )
        self.calls.append((tool, args or {}))
        return FabricateCallResult(
            status=ExternalCallStatus.SUCCESS,
            tool=tool,
            data=data,
        )


def _build_staging_sqlite() -> bytes:
    with tempfile.TemporaryDirectory(prefix="mock_fab_") as tmp:
        path = Path(tmp) / "equipment.sqlite"
        conn = sqlite3.connect(path)
        try:
            conn.executescript(
                """
                CREATE TABLE equipment (
                    tag TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    parent_tag TEXT,
                    category TEXT,
                    equipment_class TEXT,
                    criticality TEXT,
                    quantity INTEGER
                );
                CREATE TABLE components (
                    equipment_tag TEXT,
                    name TEXT,
                    quantity INTEGER
                );
                CREATE TABLE connections (
                    from_tag TEXT,
                    to_tag TEXT,
                    connection_type TEXT
                );
                INSERT INTO equipment VALUES
                    ('SYS-01', 'Plant root', NULL, 'PROCESS',
                     NULL, 'CRITICAL', 1),
                    ('P-101', 'Feed pump', 'SYS-01', 'ROTATING',
                     'Pump', 'HIGH', 1),
                    ('E-201', 'Reactor', 'SYS-01', 'STATIC',
                     'Vessel', 'CRITICAL', 1);
                INSERT INTO components VALUES ('P-101', 'Seal', 1);
                INSERT INTO connections VALUES
                    ('P-101', 'E-201', 'PROCESS');
                """
            )
            conn.commit()
        finally:
            conn.close()
        return path.read_bytes()
