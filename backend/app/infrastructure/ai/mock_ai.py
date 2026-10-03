"""Deterministic MockAIProvider for tests (no network)."""

from __future__ import annotations

import re
import time
from typing import Any

from app.application.ports import AiCompletionResult
from app.application.ports import ExternalCallStatus


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
        brief = _parse_brief(user_prompt)
        if schema_name == "plant_brief":
            return brief
        if schema_name in {"equipment_proposal", "generate_system"}:
            return {
                "brief": brief,
                "equipment": [
                    {
                        "tag": "SYS-01",
                        "name": "Plant root",
                        "category": "PROCESS",
                        "criticality": "CRITICAL",
                        "quantity": 1,
                    },
                    {
                        "tag": "P-101",
                        "name": "Feed pump",
                        "parent_tag": "SYS-01",
                        "category": "ROTATING",
                        "equipment_class": "Pump",
                        "equipment_type": "Centrifugal",
                        "criticality": "HIGH",
                        "quantity": 1,
                    },
                    {
                        "tag": "E-201",
                        "name": "Reactor",
                        "parent_tag": "SYS-01",
                        "category": "STATIC",
                        "equipment_class": "Vessel",
                        "criticality": "CRITICAL",
                        "quantity": 1,
                    },
                    {
                        "tag": "C-301",
                        "name": "Compressor",
                        "parent_tag": "SYS-01",
                        "category": "ROTATING",
                        "equipment_class": "Compressor",
                        "criticality": "HIGH",
                        "quantity": 1,
                    },
                ],
                "components": [
                    {
                        "equipment_tag": "P-101",
                        "name": "Seal",
                        "quantity": 1,
                    }
                ],
                "connections": [
                    {
                        "from_tag": "P-101",
                        "to_tag": "E-201",
                        "connection_type": "PROCESS",
                    },
                    {
                        "from_tag": "E-201",
                        "to_tag": "C-301",
                        "connection_type": "PROCESS",
                    },
                ],
                "failure_modes": [
                    {
                        "equipment_tag": "P-101",
                        "name": "Seal leakage",
                        "is_detectable": True,
                        "value_status": "UNKNOWN",
                    }
                ],
                "maintenance_tasks": [
                    {
                        "equipment_tag": "P-101",
                        "name": "Seal inspection",
                        "task_type": "INSPECTION",
                        "value_status": "UNKNOWN",
                    }
                ],
            }
        return {"ok": True, "schema_name": schema_name}


def _parse_brief(description: str) -> dict[str, Any]:
    text = description.strip() or "Unknown plant"
    capacity_match = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(тыс(?:яч)?\.?\s*)?(тонн|t\b|kt\b)",
        text,
        flags=re.IGNORECASE,
    )
    capacity_value: float | None = None
    capacity_unit: str | None = None
    if capacity_match:
        raw = capacity_match.group(1).replace(",", ".")
        capacity_value = float(raw)
        if capacity_match.group(2):
            capacity_value *= 1000.0
        capacity_unit = "t/year"
    plant_type = "process_plant"
    lowered = text.lower()
    if "полистирол" in lowered or "polystyrene" in lowered:
        plant_type = "polystyrene_plant"
    return {
        "plant_type": plant_type,
        "capacity_value": capacity_value,
        "capacity_unit": capacity_unit,
        "summary": text[:500],
        "assumptions": [
            "Synthetic structure for review only",
            "Reliability parameters remain UNKNOWN",
        ],
    }
