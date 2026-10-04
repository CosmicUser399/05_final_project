"""Unit tests for AI Analyst grounding and tool whitelist."""

from __future__ import annotations

import pytest

from app.application.analyst.grounding import build_deterministic_answer
from app.application.analyst.grounding import collect_allowed_numbers
from app.application.analyst.grounding import is_grounded
from app.application.analyst.grounding import ungounded_numbers
from app.application.analyst.tools import FORBIDDEN_TOOLS
from app.application.analyst.tools import TOOL_WHITELIST
from app.application.analyst.tools import assert_tool_allowed
from app.domain.errors import ValidationError


def test_forbidden_tools_not_in_whitelist() -> None:
    assert FORBIDDEN_TOOLS.isdisjoint(TOOL_WHITELIST)
    for name in (
        "sql.execute",
        "shell.execute",
        "filesystem.write",
    ):
        with pytest.raises(ValidationError) as exc:
            assert_tool_allowed(name)
        assert exc.value.code == "TOOL_FORBIDDEN"


def test_unknown_tool_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        assert_tool_allowed("db.execute")
    assert exc.value.code in {"TOOL_FORBIDDEN", "TOOL_NOT_ALLOWED"}


def test_grounding_rejects_invented_numbers() -> None:
    tool_payload = {
        "name": "simulation.get_metrics",
        "ok": True,
        "result": {
            "metrics": {
                "ai": {"mean": 0.91},
                "production_loss": {"mean": 12.5},
            },
            "random_seed": 42,
        },
    }
    allowed = collect_allowed_numbers([tool_payload])
    good = "Ai mean=0.91, production_loss mean=12.5, seed=42"
    bad = "Ai mean=0.99, invented MTBF=777.7"
    assert is_grounded(good, allowed)
    assert not is_grounded(bad, allowed)
    assert "777.7" in ungounded_numbers(bad, allowed)


def test_deterministic_answer_uses_tool_numbers_only() -> None:
    tools = [
        {
            "name": "simulation.get_metrics",
            "ok": True,
            "result": {
                "id": "11111111-1111-1111-1111-111111111111",
                "simulation_fingerprint": "abc",
                "random_seed": 7,
                "metrics": {
                    "ai": {"mean": 0.95, "sample_size": 10},
                    "production_loss": {"mean": 3.2, "median": 3.0},
                },
            },
        }
    ]
    answer = build_deterministic_answer(
        question="Какие потери?",
        tool_results=tools,
    )
    allowed = collect_allowed_numbers(tools)
    assert is_grounded(answer, allowed)
    assert "3.2" in answer
    assert "Потери продукции" in answer
    assert "Tool `" not in answer
    assert "777" not in answer


def test_deterministic_answer_lists_failure_modes() -> None:
    tools = [
        {
            "name": "equipment.search",
            "ok": True,
            "result": {
                "count": 1,
                "items": [
                    {
                        "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                        "tag": "P-101",
                        "name": "Feed pump",
                    }
                ],
            },
        },
        {
            "name": "failure_mode.search",
            "ok": True,
            "result": {
                "count": 1,
                "items": [
                    {
                        "equipment_id": (
                            "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
                        ),
                        "name": "Seal leakage",
                        "is_detectable": True,
                    }
                ],
            },
        },
    ]
    answer = build_deterministic_answer(
        question="Какие виды отказов у насосов учтены в модели?",
        tool_results=tools,
    )
    assert "Seal leakage" in answer
    assert "P-101" in answer
    assert "Tool `" not in answer
    assert is_grounded(answer, collect_allowed_numbers(tools))
