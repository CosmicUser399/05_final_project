"""OpenAI Chat Completions adapter (structured JSON via httpx)."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from app.application.ports import AiCompletionResult
from app.application.ports import ExternalCallStatus
from app.config import Settings

logger = logging.getLogger(__name__)

_OPENAI_URL = "https://api.openai.com/v1/chat/completions"

_BRIEF_SYSTEM = (
    "You extract a structured plant brief from a Russian or English "
    "description. Reply with JSON only."
)

_PROPOSAL_SYSTEM = (
    "You propose a technological equipment structure as JSON only. "
    "Do not invent OREDA/ISO numeric reliability parameters. "
    "Use opaque tags like P-101. Keep failure/maintenance drafts "
    "with value_status UNKNOWN. "
    "Include EVERY equipment unit named in the description "
    "(pumps, motors, pipelines, cables, tanks/vessels, etc.). "
    "Put the full user description into brief.summary. "
    "For each repairable unit add a failure_mode and a CORRECTIVE "
    "maintenance_task. Set critical equipment criticality to "
    "CRITICAL or HIGH."
)


class OpenAIProvider:
    """AIProvider backed by OpenAI Chat Completions."""

    def __init__(self, settings: Settings) -> None:
        """Bind timeout, retries and model from settings."""
        self._settings = settings
        self._model = settings.openai_model
        self._timeout = settings.openai_timeout_seconds
        self._retries = settings.openai_max_retries

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
    ) -> AiCompletionResult:
        """Call OpenAI and parse the assistant message as JSON."""
        key = self._settings.openai_api_key
        if key is None or not key.get_secret_value().strip():
            return AiCompletionResult(
                status=ExternalCallStatus.EXTERNAL_ERROR,
                model=self._model,
                message="OPENAI_API_KEY is not configured",
            )
        started = time.perf_counter()
        body = {
            "model": self._model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"schema={schema_name}\n\n{user_prompt}"
                    ),
                },
            ],
        }
        headers = {
            "Authorization": f"Bearer {key.get_secret_value()}",
            "Content-Type": "application/json",
        }
        last_error = "unknown error"
        for attempt in range(self._retries + 1):
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.post(
                        _OPENAI_URL,
                        headers=headers,
                        json=body,
                    )
                if response.status_code >= 500:
                    last_error = f"HTTP {response.status_code}"
                    continue
                if response.status_code >= 400:
                    logger.warning(
                        "openai_http_error status=%s schema=%s",
                        response.status_code,
                        schema_name,
                    )
                    return AiCompletionResult(
                        status=ExternalCallStatus.EXTERNAL_ERROR,
                        model=self._model,
                        message=f"OpenAI HTTP {response.status_code}",
                        latency_ms=_latency_ms(started),
                    )
                payload = response.json()
                return self._parse_success(payload, started)
            except httpx.TimeoutException:
                last_error = "timeout"
                logger.warning(
                    "openai_timeout attempt=%s schema=%s",
                    attempt,
                    schema_name,
                )
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                last_error = str(exc)
                logger.warning(
                    "openai_error attempt=%s schema=%s err=%s",
                    attempt,
                    schema_name,
                    type(exc).__name__,
                )
        status = (
            ExternalCallStatus.TIMEOUT
            if last_error == "timeout"
            else ExternalCallStatus.EXTERNAL_ERROR
        )
        return AiCompletionResult(
            status=status,
            model=self._model,
            message=last_error,
            latency_ms=_latency_ms(started),
        )

    def interpret_plant_description(
        self,
        description: str,
    ) -> AiCompletionResult:
        """Ask the model for a plant brief JSON object."""
        return self.complete_json(
            system_prompt=_BRIEF_SYSTEM,
            user_prompt=(
                "Return keys: plant_type, capacity_value, "
                "capacity_unit, summary, assumptions.\n"
                f"Description:\n{description}"
            ),
            schema_name="plant_brief",
        )

    def _parse_success(
        self,
        payload: dict[str, Any],
        started: float,
    ) -> AiCompletionResult:
        try:
            choice = payload["choices"][0]["message"]["content"]
            content = json.loads(choice)
            if not isinstance(content, dict):
                raise ValueError("content is not an object")
        except (KeyError, TypeError, json.JSONDecodeError, ValueError) as exc:
            return AiCompletionResult(
                status=ExternalCallStatus.VALIDATION_ERROR,
                model=self._model,
                message=f"invalid OpenAI JSON: {exc}",
                latency_ms=_latency_ms(started),
            )
        usage = payload.get("usage") or {}
        logger.info(
            "openai_ok model=%s latency_ms=%s prompt_tokens=%s "
            "completion_tokens=%s",
            self._model,
            _latency_ms(started),
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
        )
        return AiCompletionResult(
            status=ExternalCallStatus.SUCCESS,
            model=str(payload.get("model") or self._model),
            content=content,
            latency_ms=_latency_ms(started),
            prompt_tokens=_as_int(usage.get("prompt_tokens")),
            completion_tokens=_as_int(usage.get("completion_tokens")),
        )


def generate_equipment_via_openai(
    provider: OpenAIProvider,
    description: str,
) -> AiCompletionResult:
    """Return an equipment proposal completion from OpenAI."""
    return provider.complete_json(
        system_prompt=_PROPOSAL_SYSTEM,
        user_prompt=(
            "Return JSON with keys brief, equipment, components, "
            "connections, failure_modes, maintenance_tasks.\n"
            "brief must include plant_type, capacity_value, "
            "capacity_unit, summary, assumptions.\n"
            "Create one equipment row per named unit; do not "
            "collapse distinct pipelines/tanks into one row.\n"
            f"Description:\n{description}"
        ),
        schema_name="equipment_proposal",
    )


def _latency_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
