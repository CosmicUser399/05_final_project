"""Deterministic MockAIProvider for tests (no network)."""

from __future__ import annotations

import time
from typing import Any

from app.application.ports import AiCompletionResult
from app.application.ports import ExternalCallStatus
from app.infrastructure.ai.structure_from_text import (
    build_proposal_from_description,
)
from app.infrastructure.ai.structure_from_text import parse_brief


class MockAIProvider:
    """In-process AIProvider that returns a small plant structure."""

    def __init__(self, *, model: str = "mock-openai") -> None:
        """Store mock model name."""
        self._model = model
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
    ) -> AiCompletionResult:
        """Return structured JSON for known schema names."""
        started = time.perf_counter()
        self.calls.append(
            (
                "complete_json",
                {
                    "schema_name": schema_name,
                    "system_prompt": system_prompt,
                    "user_prompt": user_prompt,
                },
            )
        )
        content = self._content_for(schema_name, user_prompt)
        latency = int((time.perf_counter() - started) * 1000)
        return AiCompletionResult(
            status=ExternalCallStatus.SUCCESS,
            model=self._model,
            content=content,
            latency_ms=latency,
            prompt_tokens=len(user_prompt.split()),
            completion_tokens=64,
        )

    def interpret_plant_description(
        self,
        description: str,
    ) -> AiCompletionResult:
        """Extract a brief from free text."""
        return self.complete_json(
            system_prompt="interpret",
            user_prompt=description,
            schema_name="plant_brief",
        )

    def _content_for(
        self,
        schema_name: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        if schema_name == "plant_brief":
            return parse_brief(user_prompt)
        if schema_name == "analyst_tool_plan":
            return {"tool_calls": []}
        if schema_name == "analyst_answer":
            marker = "Base answer:\n"
            answer = user_prompt
            if marker in user_prompt:
                answer = user_prompt.split(marker, 1)[1]
                if "\ntool_results:" in answer:
                    answer = answer.split("\ntool_results:", 1)[0]
            return {"answer": answer.strip()}
        if schema_name in {"equipment_proposal", "generate_system"}:
            return build_proposal_from_description(user_prompt)
        return {"ok": True, "schema_name": schema_name}
