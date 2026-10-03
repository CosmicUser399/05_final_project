"""EquipmentProposalProvider implementations (OpenAI / Fabricate)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from app.application.ports import AIProvider
from app.application.ports import EquipmentProposalResult
from app.application.ports import ExternalCallStatus
from app.application.ports import FabricateProvider
from app.domain.ai.dto import EquipmentProposalPayload
from app.domain.errors import ValidationError
from app.infrastructure.ai.mock_ai import MockAIProvider
from app.infrastructure.ai.openai_provider import OpenAIProvider
from app.infrastructure.ai.openai_provider import generate_equipment_via_openai
from app.infrastructure.files.staging_importer import StagingImporter
from app.infrastructure.files.staging_schema import STAGING_SCHEMA_VERSION


class OpenAIEquipmentProvider:
    """Fast path: structured equipment proposal via OpenAI/Mock AI."""

    def __init__(self, ai: AIProvider) -> None:
        """Bind an AIProvider implementation."""
        self._ai = ai

    def generate_proposal(
        self,
        description: str,
        *,
        schema_version: str = "1",
    ) -> EquipmentProposalResult:
        """Generate a proposal JSON payload without touching Domain DB."""
        _ = schema_version
        if isinstance(self._ai, OpenAIProvider):
            result = generate_equipment_via_openai(self._ai, description)
        else:
            result = self._ai.complete_json(
                system_prompt="equipment_proposal",
                user_prompt=description,
                schema_name="equipment_proposal",
            )
        if result.status is not ExternalCallStatus.SUCCESS:
            return EquipmentProposalResult(
                status=result.status,
                message=result.message,
                ai_model=result.model,
                latency_ms=result.latency_ms,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
            )
        try:
            payload = EquipmentProposalPayload.model_validate(result.content)
        except Exception as exc:  # noqa: BLE001 - map to typed result
            return EquipmentProposalResult(
                status=ExternalCallStatus.VALIDATION_ERROR,
                message=f"invalid proposal DTO: {exc}",
                ai_model=result.model,
            )
        return EquipmentProposalResult(
            status=ExternalCallStatus.SUCCESS,
            payload=payload.model_dump(mode="json"),
            ai_model=result.model,
            latency_ms=result.latency_ms,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            metadata={"provider": "openai"},
        )


class FabricateEquipmentProvider:
    """Async-capable Fabricate path: upload schema, poll, import staging."""

    def __init__(
        self,
        fabricate: FabricateProvider,
        *,
        importer: StagingImporter | None = None,
        schema_doc_path: Path | None = None,
        max_polls: int = 60,
        poll_sleep_seconds: float = 0.0,
    ) -> None:
        """Bind Fabricate adapter and staging importer."""
        self._fabricate = fabricate
        self._importer = importer or StagingImporter()
        self._schema_doc_path = schema_doc_path
        self._max_polls = max_polls
        self._poll_sleep = poll_sleep_seconds

    def generate_proposal(
        self,
        description: str,
        *,
        schema_version: str = "1",
    ) -> EquipmentProposalResult:
        """Run Fabricate conversation to a staging proposal payload."""
        options = self._fabricate.list_conversation_options()
        if options.status is not ExternalCallStatus.SUCCESS:
            return _from_fab(options.status, options.message)

        schema_bytes = self._schema_bytes(schema_version)
        upload = self._fabricate.create_upload(
            filename="fabricate-staging-schema.md",
            content=schema_bytes,
            content_type="text/markdown",
        )
        if upload.status is not ExternalCallStatus.SUCCESS:
            return _from_fab(upload.status, upload.message)
        upload_id = str(upload.data.get("upload_id") or "")
        if not upload_id:
            return EquipmentProposalResult(
                status=ExternalCallStatus.VALIDATION_ERROR,
                message="create_upload returned no upload_id",
            )

        model: str | None = None
        opts_models = options.data.get("models") or []
        if isinstance(opts_models, list) and opts_models:
            first = opts_models[0]
            if isinstance(first, dict):
                model = str(first.get("id") or "") or None

        started = self._fabricate.start_conversation(
            message=(
                "Generate a relational equipment database for the plant "
                "described below. Follow the attached staging schema "
                "file; do not invent reliability numeric parameters.\n\n"
                f"{description.strip()}"
            ),
            upload_ids=[upload_id],
            model=model,
            mode="autonomous",
            approach="dataset",
        )
        if started.status is not ExternalCallStatus.SUCCESS:
            return _from_fab(started.status, started.message)
        conversation_id = str(started.data.get("conversation_id") or "")
        if not conversation_id:
            return EquipmentProposalResult(
                status=ExternalCallStatus.VALIDATION_ERROR,
                message="start_conversation returned no conversation_id",
            )

        for _ in range(self._max_polls):
            status = self._fabricate.get_conversation_status(conversation_id)
            if status.status is not ExternalCallStatus.SUCCESS:
                return _from_fab(
                    status.status,
                    status.message,
                    conversation_id=conversation_id,
                )
            state = str(status.data.get("status") or "").lower()
            if state in {"cancelled", "canceled", "failed", "error"}:
                return EquipmentProposalResult(
                    status=ExternalCallStatus.FAILURE,
                    message=f"conversation ended with status={state}",
                    conversation_id=conversation_id,
                )
            if state in {"completed", "complete", "succeeded", "success"}:
                break
            if self._poll_sleep > 0:
                time.sleep(self._poll_sleep)
        else:
            return EquipmentProposalResult(
                status=ExternalCallStatus.TIMEOUT,
                message="Fabricate conversation poll timed out",
                conversation_id=conversation_id,
            )

        result = self._fabricate.get_conversation_result(conversation_id)
        if result.status is not ExternalCallStatus.SUCCESS:
            return _from_fab(
                result.status,
                result.message,
                conversation_id=conversation_id,
            )
        file_id = _first_file_id(result.data)
        if not file_id:
            return EquipmentProposalResult(
                status=ExternalCallStatus.VALIDATION_ERROR,
                message="no downloadable SQLite artifact in result",
                conversation_id=conversation_id,
            )
        download = self._fabricate.download_conversation_file(
            conversation_id=conversation_id,
            file_id=file_id,
        )
        if download.status is not ExternalCallStatus.SUCCESS:
            return _from_fab(
                download.status,
                download.message,
                conversation_id=conversation_id,
            )
        blob = download.data.get("bytes")
        if not isinstance(blob, (bytes, bytearray)):
            return EquipmentProposalResult(
                status=ExternalCallStatus.VALIDATION_ERROR,
                message="download did not include artifact bytes",
                conversation_id=conversation_id,
            )
        try:
            payload = self._importer.import_bytes(
                bytes(blob),
                conversation_id=conversation_id,
            )
        except ValidationError as exc:
            return EquipmentProposalResult(
                status=ExternalCallStatus.VALIDATION_ERROR,
                message=exc.message,
                conversation_id=conversation_id,
            )
        return EquipmentProposalResult(
            status=ExternalCallStatus.SUCCESS,
            payload=payload.model_dump(mode="json"),
            conversation_id=conversation_id,
            metadata={
                "provider": "fabricate",
                "staging_schema_version": schema_version
                or STAGING_SCHEMA_VERSION,
            },
        )

    def _schema_bytes(self, schema_version: str) -> bytes:
        if self._schema_doc_path and self._schema_doc_path.is_file():
            return self._schema_doc_path.read_bytes()
        spec = {
            "schema_version": schema_version or STAGING_SCHEMA_VERSION,
            "tables": [
                "equipment",
                "components",
                "connections",
                "failure_modes",
                "maintenance_tasks",
            ],
            "notes": (
                "See docs/api/fabricate-staging-schema.md. "
                "Do not include reliability numeric parameters."
            ),
        }
        return json.dumps(spec, ensure_ascii=True, indent=2).encode("utf-8")


class MockEquipmentProposalProvider:
    """Thin wrapper over MockAIProvider for tests."""

    def __init__(self) -> None:
        """Create an OpenAIEquipmentProvider over MockAI."""
        self._inner = OpenAIEquipmentProvider(MockAIProvider())

    def generate_proposal(
        self,
        description: str,
        *,
        schema_version: str = "1",
    ) -> EquipmentProposalResult:
        """Delegate to the OpenAI mock path."""
        return self._inner.generate_proposal(
            description,
            schema_version=schema_version,
        )


def _from_fab(
    status: ExternalCallStatus,
    message: str | None,
    *,
    conversation_id: str | None = None,
) -> EquipmentProposalResult:
    return EquipmentProposalResult(
        status=status,
        message=message,
        conversation_id=conversation_id,
        metadata={"provider": "fabricate"},
    )


def _first_file_id(data: dict[str, Any]) -> str | None:
    files = data.get("files")
    if isinstance(files, list):
        for item in files:
            if isinstance(item, dict) and item.get("file_id"):
                return str(item["file_id"])
    file_id = data.get("file_id")
    return str(file_id) if file_id else None
