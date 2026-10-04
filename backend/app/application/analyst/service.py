"""AI Analyst orchestrator: plan tools, execute, ground answer."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from collections.abc import Iterator
from typing import Any
from uuid import UUID

from app.application.analyst.context import AnalystChatContext
from app.application.analyst.context import AnalystChatRequest
from app.application.analyst.context import AnalystChatResponse
from app.application.analyst.context import AnalystReference
from app.application.analyst.context import AnalystToolCallRecord
from app.application.analyst.grounding import build_deterministic_answer
from app.application.analyst.grounding import collect_allowed_numbers
from app.application.analyst.grounding import is_grounded
from app.application.analyst.grounding import ungounded_numbers
from app.application.analyst.tools import TOOL_SPECS
from app.application.analyst.tools import AnalystToolExecutor
from app.application.analyst.tools import PlannedToolCall
from app.application.ports import AIProvider
from app.application.ports import ExternalCallStatus
from app.domain.errors import DomainError
from app.domain.errors import NotFoundError
from app.domain.errors import ValidationError

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, dict[str, Any]], None]


class AiAnalystService:
    """Answer questions using only typed tools + grounding."""

    def __init__(
        self,
        *,
        tools: AnalystToolExecutor,
        ai: AIProvider,
    ) -> None:
        """Bind tool executor and optional LLM planner."""
        self._tools = tools
        self._ai = ai

    def chat(
        self,
        request: AnalystChatRequest,
        *,
        on_progress: ProgressCallback | None = None,
    ) -> AnalystChatResponse:
        """Plan tools, execute them, return a grounded answer."""

        def emit(event: str, data: dict[str, Any]) -> None:
            if on_progress is not None:
                on_progress(event, data)

        emit("started", {"message": request.message})
        planned = self._plan_tools(request)
        emit(
            "planned",
            {
                "tools": [
                    {"name": call.name, "arguments": call.arguments}
                    for call in planned
                ],
            },
        )

        records: list[AnalystToolCallRecord] = []
        for call in planned:
            emit(
                "tool_start",
                {"name": call.name, "arguments": call.arguments},
            )
            record = self._run_tool(call)
            records.append(record)
            emit(
                "tool_result",
                {
                    "name": record.name,
                    "ok": record.ok,
                    "error": record.error,
                },
            )

        answer = self._synthesize(request, records)
        allowed = collect_allowed_numbers(
            [row.model_dump(mode="json") for row in records]
        )
        grounded = is_grounded(answer, allowed)
        if not grounded:
            bad = ungounded_numbers(answer, allowed)
            logger.warning(
                "analyst_ungrounded numbers=%s; falling back",
                bad,
            )
            answer = build_deterministic_answer(
                question=request.message,
                tool_results=[row.model_dump(mode="json") for row in records],
            )
            grounded = True

        references = self._build_references(request.context, records)
        response = AnalystChatResponse(
            answer=answer,
            references=references,
            tool_calls=records,
            grounded=grounded,
            model=_provider_model(self._ai),
        )
        emit(
            "done",
            {
                "grounded": response.grounded,
                "tool_count": len(records),
                "reference_count": len(references),
            },
        )
        return response

    def iter_sse_events(
        self,
        request: AnalystChatRequest,
    ) -> Iterator[tuple[str, dict[str, Any]]]:
        """Yield SSE (event, payload) pairs while answering."""
        queue: list[tuple[str, dict[str, Any]]] = []

        def on_progress(event: str, data: dict[str, Any]) -> None:
            queue.append((event, data))

        response = self.chat(request, on_progress=on_progress)
        yield from queue
        yield ("answer", response.model_dump(mode="json"))

    def _plan_tools(
        self,
        request: AnalystChatRequest,
    ) -> list[PlannedToolCall]:
        heuristic = _heuristic_plan(request)
        llm_plan = self._llm_plan(request)
        if not llm_plan:
            return heuristic
        # Prefer LLM plan but keep heuristic fallbacks for required ids.
        merged = _merge_plans(llm_plan, heuristic)
        return merged or heuristic

    def _llm_plan(
        self,
        request: AnalystChatRequest,
    ) -> list[PlannedToolCall]:
        tool_names = [spec.name for spec in TOOL_SPECS]
        ctx = request.context.model_dump(mode="json")
        prompt = (
            "Select typed tools to answer the user. Return JSON "
            '{"tool_calls":[{"name":"...","arguments":{...}}]}. '
            f"Allowed tools: {tool_names}. "
            "Do not invent ids; use context ids when present. "
            f"Context: {ctx}\nQuestion: {request.message}"
        )
        try:
            result = self._ai.complete_json(
                system_prompt=(
                    "You are an AI Analyst planner. Choose only "
                    "whitelisted read tools. Never invent metrics."
                ),
                user_prompt=prompt,
                schema_name="analyst_tool_plan",
            )
        except Exception:  # noqa: BLE001 - planner must not break chat
            logger.warning("analyst_llm_plan_failed", exc_info=True)
            return []
        if result.status != ExternalCallStatus.SUCCESS:
            return []
        raw_calls = result.content.get("tool_calls")
        if not isinstance(raw_calls, list):
            return []
        planned: list[PlannedToolCall] = []
        for item in raw_calls:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if name not in {spec.name for spec in TOOL_SPECS}:
                continue
            arguments = item.get("arguments") or {}
            if not isinstance(arguments, dict):
                arguments = {}
            planned.append(PlannedToolCall(name=name, arguments=arguments))
        return planned

    def _run_tool(
        self,
        call: PlannedToolCall,
    ) -> AnalystToolCallRecord:
        try:
            result = self._tools.execute(call.name, call.arguments)
            return AnalystToolCallRecord(
                name=call.name,
                arguments=call.arguments,
                ok=True,
                result=result,
            )
        except (DomainError, NotFoundError, ValidationError) as exc:
            return AnalystToolCallRecord(
                name=call.name,
                arguments=call.arguments,
                ok=False,
                error=str(exc),
            )

    def _synthesize(
        self,
        request: AnalystChatRequest,
        records: list[AnalystToolCallRecord],
    ) -> str:
        tool_payloads = [row.model_dump(mode="json") for row in records]
        base = build_deterministic_answer(
            question=request.message,
            tool_results=tool_payloads,
        )
        # Optional LLM polish; grounding gate rejects inventions.
        polished = self._llm_polish(request.message, tool_payloads, base)
        if polished is None:
            return base
        allowed = collect_allowed_numbers(tool_payloads)
        if is_grounded(polished, allowed):
            return polished
        return base

    def _llm_polish(
        self,
        question: str,
        tool_payloads: list[dict[str, Any]],
        base_answer: str,
    ) -> str | None:
        prompt = (
            "Rewrite the factual answer in clear Russian. "
            "Use ONLY numbers that appear in tool_results. "
            "If a number is missing, say data is unavailable. "
            'Return JSON {"answer": "..."}.\n'
            f"Question: {question}\n"
            f"Base answer:\n{base_answer}\n"
            f"tool_results:\n{tool_payloads}"
        )
        try:
            result = self._ai.complete_json(
                system_prompt=(
                    "You synthesize RAM analysis. Never invent "
                    "numeric results; cite only tool_results."
                ),
                user_prompt=prompt,
                schema_name="analyst_answer",
            )
        except Exception:  # noqa: BLE001
            return None
        if result.status != ExternalCallStatus.SUCCESS:
            return None
        answer = result.content.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            return None
        return answer.strip()

    def _build_references(
        self,
        context: AnalystChatContext,
        records: list[AnalystToolCallRecord],
    ) -> list[AnalystReference]:
        refs: list[AnalystReference] = []
        seen: set[tuple[str, str | None]] = set()

        def add(
            kind: str,
            entity_id: str | None,
            label: str,
            detail: dict[str, Any] | None = None,
        ) -> None:
            key = (kind, entity_id)
            if key in seen:
                return
            seen.add(key)
            refs.append(
                AnalystReference(
                    kind=kind,
                    entity_id=entity_id,
                    label=label,
                    detail=detail or {},
                )
            )

        if context.simulation_run_id is not None:
            add(
                "simulation",
                str(context.simulation_run_id),
                "Simulation run",
            )
        if context.scenario_id is not None:
            add(
                "scenario",
                str(context.scenario_id),
                "Scenario",
            )
        if context.version_id is not None:
            add(
                "system_version",
                str(context.version_id),
                "System version",
            )
        if context.system_id is not None:
            add(
                "system",
                str(context.system_id),
                "System",
            )
        if context.equipment_id is not None:
            add(
                "equipment",
                str(context.equipment_id),
                "Selected equipment",
            )

        for record in records:
            if not record.ok:
                continue
            result = record.result
            if record.name == "simulation.get_metrics":
                add(
                    "simulation",
                    str(result.get("id") or ""),
                    "Simulation metrics",
                    {
                        "simulation_fingerprint": result.get(
                            "simulation_fingerprint"
                        ),
                        "model_hash": result.get("model_hash"),
                        "scenario_hash": result.get("scenario_hash"),
                        "random_seed": result.get("random_seed"),
                    },
                )
            elif record.name == "simulation.compare":
                add(
                    "scenario_comparison",
                    str(result.get("scenario_id") or ""),
                    "Scenario comparison",
                    {
                        "baseline_run_id": result.get("baseline_run_id"),
                        "scenario_run_id": result.get("scenario_run_id"),
                    },
                )
            elif record.name == "system.get":
                system = result.get("system") or {}
                version = result.get("version") or {}
                if system.get("id"):
                    add(
                        "system",
                        str(system["id"]),
                        f"System {system.get('name')}",
                    )
                if version.get("id"):
                    add(
                        "system_version",
                        str(version["id"]),
                        "System version",
                        {"status": version.get("status")},
                    )
            elif record.name == "scenario.get":
                add(
                    "scenario",
                    str(result.get("id") or ""),
                    f"Scenario {result.get('name')}",
                )
            add("tool", record.name, f"Tool {record.name}")
        return refs


def _heuristic_plan(
    request: AnalystChatRequest,
) -> list[PlannedToolCall]:
    text = request.message.lower()
    ctx = request.context
    planned: list[PlannedToolCall] = []

    wants_compare = (
        bool(re.search(r"сравн|delta|Δ|разниц", text, flags=re.I))
        or "compare" in text
    )
    wants_events = bool(re.search(r"событ|event|журнал|лог", text, flags=re.I))
    wants_metrics = bool(
        re.search(
            r"доступн|availab|mtbf|mttr|потер|loss|метрик|"
            r"ai\b|ao\b|pareto|отказ|production",
            text,
            flags=re.I,
        )
    )
    wants_equipment = bool(
        re.search(r"оборуд|equipment|насос|tag|единиц", text, flags=re.I)
    )
    wants_fm = bool(
        re.search(r"failure|отказн|режим отказа", text, flags=re.I)
    )
    wants_maint = bool(
        re.search(r"то\b|ремонт|maintenance|обслужив", text, flags=re.I)
    )
    wants_ref = bool(
        re.search(r"oreda|iso\s*14224|reference|справочн", text, flags=re.I)
    )
    wants_system = bool(re.search(r"систем|version|верси", text, flags=re.I))
    wants_scenario = bool(re.search(r"сценар", text, flags=re.I))

    if wants_compare and ctx.scenario_id is not None:
        planned.append(
            PlannedToolCall(
                name="simulation.compare",
                arguments={"scenario_id": str(ctx.scenario_id)},
            )
        )
    if (
        (wants_metrics or not planned)
        and ctx.simulation_run_id is not None
        and not wants_compare
    ):
        planned.append(
            PlannedToolCall(
                name="simulation.get_metrics",
                arguments={
                    "simulation_run_id": str(ctx.simulation_run_id),
                },
            )
        )
    if wants_events and ctx.simulation_run_id is not None:
        args: dict[str, Any] = {
            "simulation_run_id": str(ctx.simulation_run_id),
            "limit": 50,
        }
        if ctx.equipment_id is not None:
            args["equipment_id"] = str(ctx.equipment_id)
        planned.append(
            PlannedToolCall(
                name="simulation.get_events",
                arguments=args,
            )
        )
    if wants_scenario and ctx.scenario_id is not None:
        planned.append(
            PlannedToolCall(
                name="scenario.get",
                arguments={"scenario_id": str(ctx.scenario_id)},
            )
        )
    if wants_system and (
        ctx.system_id is not None or ctx.version_id is not None
    ):
        args = {}
        if ctx.system_id is not None:
            args["system_id"] = str(ctx.system_id)
        if ctx.version_id is not None:
            args["version_id"] = str(ctx.version_id)
        planned.append(PlannedToolCall(name="system.get", arguments=args))
    if wants_equipment and ctx.version_id is not None:
        args = {"version_id": str(ctx.version_id), "limit": 50}
        if ctx.equipment_id is not None:
            args["equipment_id"] = str(ctx.equipment_id)
        query = _extract_query_token(request.message)
        if query:
            args["query"] = query
        planned.append(
            PlannedToolCall(name="equipment.search", arguments=args)
        )
    if wants_fm and ctx.version_id is not None:
        args = {"version_id": str(ctx.version_id), "limit": 50}
        if ctx.equipment_id is not None:
            args["equipment_id"] = str(ctx.equipment_id)
        planned.append(
            PlannedToolCall(
                name="failure_mode.search",
                arguments=args,
            )
        )
    if wants_maint and ctx.version_id is not None:
        args = {"version_id": str(ctx.version_id), "limit": 50}
        if ctx.equipment_id is not None:
            args["equipment_id"] = str(ctx.equipment_id)
        planned.append(
            PlannedToolCall(
                name="maintenance.search",
                arguments=args,
            )
        )
    if wants_ref:
        planned.append(
            PlannedToolCall(
                name="reference.search",
                arguments={
                    "query": request.message[:200],
                    "limit": 20,
                },
            )
        )

    if not planned and ctx.simulation_run_id is not None:
        planned.append(
            PlannedToolCall(
                name="simulation.get_metrics",
                arguments={
                    "simulation_run_id": str(ctx.simulation_run_id),
                },
            )
        )
    if not planned and ctx.version_id is not None:
        planned.append(
            PlannedToolCall(
                name="equipment.search",
                arguments={
                    "version_id": str(ctx.version_id),
                    "limit": 20,
                },
            )
        )
    if not planned and (
        ctx.system_id is not None or ctx.version_id is not None
    ):
        args = {}
        if ctx.system_id is not None:
            args["system_id"] = str(ctx.system_id)
        if ctx.version_id is not None:
            args["version_id"] = str(ctx.version_id)
        planned.append(PlannedToolCall(name="system.get", arguments=args))
    return planned


def _merge_plans(
    primary: list[PlannedToolCall],
    secondary: list[PlannedToolCall],
) -> list[PlannedToolCall]:
    seen: set[str] = set()
    merged: list[PlannedToolCall] = []
    for call in primary + secondary:
        key = f"{call.name}:{sorted(call.arguments.items())}"
        if key in seen:
            continue
        seen.add(key)
        merged.append(call)
    return merged


def _extract_query_token(message: str) -> str | None:
    match = re.search(
        r"\b([A-Z]{1,4}-\d{2,4})\b",
        message,
        flags=re.I,
    )
    if match:
        return match.group(1)
    return None


def parse_uuid(raw: str | UUID | None) -> UUID | None:
    """Parse optional UUID string."""
    if raw is None or str(raw).strip() == "":
        return None
    return UUID(str(raw))


def _provider_model(ai: AIProvider) -> str | None:
    model = getattr(ai, "_model", None)
    if isinstance(model, str) and model.strip():
        return model
    return None
