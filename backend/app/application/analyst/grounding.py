"""Ground answers so numeric claims come only from tool results."""

from __future__ import annotations

import json
import re
from typing import Any

_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9_/.-])"
    r"(-?(?:\d+\.\d+|\d+)(?:[eE][+-]?\d+)?)"
    r"(?![A-Za-z0-9_/.-])"
)

# Tolerances for float comparison when grounding.
_ABS_TOL = 1e-9
_REL_TOL = 1e-6


def collect_allowed_numbers(payload: Any) -> set[str]:
    """Collect canonical string forms of numbers found in tool JSON."""
    allowed: set[str] = set()
    _walk(payload, allowed)
    return allowed


def extract_numbers_from_text(text: str) -> list[str]:
    """Return number tokens found in free text (as written)."""
    return [match.group(1) for match in _NUMBER_RE.finditer(text)]


def is_grounded(answer: str, allowed: set[str]) -> bool:
    """Return True if every number in answer is in tool data."""
    if not answer.strip():
        return True
    for token in extract_numbers_from_text(answer):
        if not _token_allowed(token, allowed):
            return False
    return True


def ungounded_numbers(answer: str, allowed: set[str]) -> list[str]:
    """List number tokens in answer that are not in tool data."""
    bad: list[str] = []
    for token in extract_numbers_from_text(answer):
        if not _token_allowed(token, allowed):
            bad.append(token)
    return bad


def build_deterministic_answer(
    *,
    question: str,
    tool_results: list[dict[str, Any]],
) -> str:
    """Compose a Russian answer using only tool payloads (no LLM)."""
    _ = question
    if not tool_results:
        return (
            "Недостаточно данных в контексте. Укажите симуляцию, "
            "сценарий или версию системы и повторите вопрос."
        )

    lines: list[str] = [
        "Ответ построен только по результатам typed tools "
        "(без вымышленных чисел).",
        "",
    ]
    for entry in tool_results:
        name = str(entry.get("name") or "tool")
        if not entry.get("ok"):
            err = entry.get("error") or "ошибка"
            lines.append(f"- {name}: недоступно ({err}).")
            continue
        result = entry.get("result") or {}
        lines.extend(_summarize_tool(name, result))
    return "\n".join(lines).strip()


def _summarize_tool(name: str, result: dict[str, Any]) -> list[str]:
    lines: list[str] = [f"- Tool `{name}`:"]
    if name == "simulation.get_metrics":
        metrics = result.get("metrics") or {}
        fingerprint = result.get("simulation_fingerprint")
        seed = result.get("random_seed")
        lines.append(f"  simulation_fingerprint={fingerprint}, seed={seed}.")
        for key in (
            "ai",
            "ao",
            "production_loss",
            "mtbf_minutes",
            "mttr_minutes",
            "reliability_at_horizon",
        ):
            value = metrics.get(key)
            if value is None:
                continue
            lines.append(f"  {key}={_compact_json(value)}")
        pareto = metrics.get("failure_pareto") or []
        if pareto:
            top = pareto[:5]
            lines.append(f"  failure_pareto={_compact_json(top)}")
        equipment = metrics.get("equipment") or []
        if equipment:
            lines.append(f"  equipment={_compact_json(equipment[:5])}")
        return lines

    if name == "simulation.compare":
        deltas = {
            "availability_delta": result.get("availability_delta"),
            "production_loss_delta": result.get("production_loss_delta"),
            "maintenance_cost_delta": result.get("maintenance_cost_delta"),
        }
        lines.append(f"  deltas={_compact_json(deltas)}")
        for key in (
            "baseline_run_id",
            "scenario_run_id",
            "scenario_id",
        ):
            if result.get(key) is not None:
                lines.append(f"  {key}={result.get(key)}")
        return lines

    if name == "simulation.get_events":
        lines.append(
            f"  events_page count={result.get('count')}, "
            f"offset={result.get('offset')}, "
            f"limit={result.get('limit')}."
        )
        return lines

    if name in {
        "equipment.search",
        "failure_mode.search",
        "maintenance.search",
        "reference.search",
    }:
        lines.append(
            f"  count={result.get('count')}, query={result.get('query')!r}."
        )
        if result.get("message"):
            lines.append(f"  note={result.get('message')}")
        items = result.get("items") or []
        for item in items[:10]:
            label = (
                item.get("tag") or item.get("name") or item.get("id") or item
            )
            lines.append(f"  - {_compact_json(label)}")
        return lines

    if name == "system.get":
        system = result.get("system") or {}
        version = result.get("version") or {}
        if system:
            lines.append(
                f"  system name={system.get('name')!r} id={system.get('id')}."
            )
        if version:
            lines.append(
                f"  version number={version.get('version_number')} "
                f"status={version.get('status')} "
                f"id={version.get('id')}."
            )
        return lines

    if name == "scenario.get":
        lines.append(
            f"  scenario name={result.get('name')!r} id={result.get('id')}."
        )
        changes = result.get("changes") or result.get("current_changes") or []
        if changes:
            lines.append(f"  changes={_compact_json(changes[:5])}")
        return lines

    lines.append(f"  payload={_compact_json(result)}")
    return lines


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _walk(node: Any, allowed: set[str]) -> None:
    if isinstance(node, bool) or node is None:
        return
    if isinstance(node, int | float):
        allowed.add(_canon(node))
        return
    if isinstance(node, str):
        for token in extract_numbers_from_text(node):
            allowed.add(_canon_token(token))
        return
    if isinstance(node, dict):
        for value in node.values():
            _walk(value, allowed)
        return
    if isinstance(node, list | tuple):
        for item in node:
            _walk(item, allowed)


def _canon(value: int | float) -> str:
    if isinstance(value, bool):
        return str(value)
    as_float = float(value)
    if as_float.is_integer() and abs(as_float) < 1e15:
        return str(int(as_float))
    return format(as_float, ".12g")


def _canon_token(token: str) -> str:
    try:
        if "." in token or "e" in token.lower():
            return _canon(float(token))
        return _canon(int(token))
    except ValueError:
        return token


def _token_allowed(token: str, allowed: set[str]) -> bool:
    canon = _canon_token(token)
    if canon in allowed or token in allowed:
        return True
    try:
        value = float(token)
    except ValueError:
        return False
    for item in allowed:
        try:
            other = float(item)
        except ValueError:
            continue
        if _floats_close(value, other):
            return True
    return False


def _floats_close(a: float, b: float) -> bool:
    if a == b:
        return True
    diff = abs(a - b)
    if diff <= _ABS_TOL:
        return True
    scale = max(abs(a), abs(b), 1.0)
    return diff / scale <= _REL_TOL
