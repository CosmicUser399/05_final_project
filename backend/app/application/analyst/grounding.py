"""Ground answers so numeric claims come only from tool results."""

from __future__ import annotations

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
    """Compose a readable Russian answer from tool payloads only."""
    if not tool_results:
        return (
            "Недостаточно данных в контексте. Укажите симуляцию, "
            "сценарий или версию системы и повторите вопрос."
        )

    labels = _equipment_labels(tool_results)
    ok_results = [
        entry
        for entry in tool_results
        if entry.get("ok") and isinstance(entry.get("result"), dict)
    ]
    if not ok_results and tool_results:
        lines = ["Не удалось получить данные по запросу:"]
        for entry in tool_results:
            name = str(entry.get("name") or "tool")
            err = entry.get("error") or "ошибка"
            lines.append(f"- {name}: {err}")
        return "\n".join(lines)

    q = question.lower()
    sections: list[str] = []

    if _asks_failure_modes(q):
        section = _answer_failure_modes(ok_results, labels, q)
        if section:
            sections.append(section)
    if _asks_production_loss(q):
        section = _answer_production_loss(ok_results)
        if section:
            sections.append(section)
    if _asks_availability(q):
        section = _answer_availability(ok_results)
        if section:
            sections.append(section)
    if _asks_equipment(q):
        section = _answer_equipment(ok_results, q)
        if section:
            sections.append(section)

    if not sections:
        for entry in ok_results:
            name = str(entry.get("name") or "tool")
            result = entry.get("result") or {}
            section = _summarize_tool_readable(name, result, labels)
            if section:
                sections.append(section)

    if not sections:
        return (
            "По выбранному контексту нет данных, отвечающих на вопрос. "
            "Проверьте симуляцию, версию модели и формулировку."
        )
    return "\n\n".join(sections).strip()


def _asks_failure_modes(q: str) -> bool:
    return bool(
        re.search(
            r"failure\s*mode|вид\w*\s+отказ|режим\w*\s+отказ|"
            r"отказн\w*|modes?",
            q,
            flags=re.I,
        )
    )


def _asks_production_loss(q: str) -> bool:
    return bool(
        re.search(
            r"потер|production|не выпущ|недовыпуск|продукц",
            q,
            flags=re.I,
        )
    )


def _asks_availability(q: str) -> bool:
    return bool(
        re.search(
            r"доступн|availab|\bai\b|\bao\b|mtbf|mttr|метрик|"
            r"над[её]жн",
            q,
            flags=re.I,
        )
    )


def _asks_equipment(q: str) -> bool:
    return bool(re.search(r"оборуд|equipment|насос|tag|единиц", q, flags=re.I))


def _answer_failure_modes(
    ok_results: list[dict[str, Any]],
    labels: dict[str, str],
    question: str,
) -> str | None:
    items: list[dict[str, Any]] = []
    for entry in ok_results:
        if entry.get("name") != "failure_mode.search":
            continue
        result = entry.get("result") or {}
        items.extend(result.get("items") or [])
    if not items:
        # Fall back: mention that modes tool was not available.
        for entry in ok_results:
            if entry.get("name") == "equipment.search":
                eq = _answer_equipment(ok_results, question)
                if eq:
                    return (
                        "В ответе нет перечня видов отказов: "
                        "нужен инструмент failure_mode.search. "
                        f"Найденное оборудование:\n{eq}"
                    )
        return (
            "Виды отказов в контексте не найдены. "
            "Укажите версию системы и повторите вопрос."
        )

    if re.search(r"насос|pump", question, flags=re.I):
        pump_ids = {
            eid for eid, label in labels.items() if _looks_like_pump(label)
        }
        if pump_ids:
            items = [
                item
                for item in items
                if str(item.get("equipment_id") or "") in pump_ids
            ]

    if not items:
        return (
            "Для насосов в выбранной версии виды отказов не найдены "
            "(или оборудование не сопоставлено)."
        )

    lines = ["Виды отказов в модели:"]
    by_eq: dict[str, list[str]] = {}
    for item in items:
        eid = str(item.get("equipment_id") or "")
        label = labels.get(eid) or eid or "оборудование"
        name = str(item.get("name") or "без названия")
        detectable = item.get("is_detectable")
        suffix = ""
        if detectable is True:
            suffix = " (обнаруживаемый)"
        elif detectable is False:
            suffix = " (необнаруживаемый)"
        by_eq.setdefault(label, []).append(f"{name}{suffix}")

    for label, modes in sorted(by_eq.items()):
        lines.append(f"- {label}:")
        for mode_name in modes:
            lines.append(f"  • {mode_name}")
    return "\n".join(lines)


def _answer_production_loss(
    ok_results: list[dict[str, Any]],
) -> str | None:
    metrics_payload = _first_metrics(ok_results)
    if metrics_payload is None:
        return None
    metrics, seed = metrics_payload
    loss = metrics.get("production_loss")
    if not isinstance(loss, dict):
        return "В результатах симуляции нет метрики production_loss."
    lines = [
        f"Потери продукции из-за простоев (симуляция, seed={_fmt(seed)}):",
        *_format_stat_block(loss, unit="ед. продукции"),
    ]
    return "\n".join(lines)


def _answer_availability(
    ok_results: list[dict[str, Any]],
) -> str | None:
    metrics_payload = _first_metrics(ok_results)
    if metrics_payload is None:
        return None
    metrics, seed = metrics_payload
    lines = [
        f"Ключевые метрики симуляции (seed={_fmt(seed)}):",
    ]
    for key, title in (
        ("ai", "Доступность Ai"),
        ("ao", "Операционная доступность Ao"),
        ("mtbf_minutes", "MTBF"),
        ("mttr_minutes", "MTTR"),
        ("production_loss", "Потери продукции"),
    ):
        value = metrics.get(key)
        if isinstance(value, dict):
            unit = "мин" if "minutes" in key else None
            lines.append(f"{title}:")
            lines.extend(_format_stat_block(value, unit=unit, indent="  "))
    rel = metrics.get("reliability_at_horizon")
    if isinstance(rel, dict) and rel.get("value") is not None:
        lines.append(
            "Надёжность на горизонте: "
            f"value={_fmt(rel.get('value'))}, "
            f"successes={_fmt(rel.get('successes'))}, "
            f"trials={_fmt(rel.get('trials'))}."
        )
    return "\n".join(lines)


def _answer_equipment(
    ok_results: list[dict[str, Any]],
    question: str,
) -> str | None:
    items: list[dict[str, Any]] = []
    for entry in ok_results:
        if entry.get("name") != "equipment.search":
            continue
        result = entry.get("result") or {}
        items.extend(result.get("items") or [])
    if not items:
        return None
    if re.search(r"насос|pump", question, flags=re.I):
        filtered = [
            item
            for item in items
            if _looks_like_pump(
                f"{item.get('tag') or ''} {item.get('name') or ''}"
            )
        ]
        if filtered:
            items = filtered
    count = None
    for entry in ok_results:
        if entry.get("name") == "equipment.search":
            count = (entry.get("result") or {}).get("count")
            break
    header = "Оборудование в версии"
    if count is not None:
        header = f"Оборудование в версии (count={_fmt(count)})"
    lines = [f"{header}:"]
    for item in items[:20]:
        tag = item.get("tag") or "?"
        name = item.get("name") or ""
        lines.append(f"- {tag}" + (f" — {name}" if name else ""))
    return "\n".join(lines)


def _summarize_tool_readable(
    name: str,
    result: dict[str, Any],
    labels: dict[str, str],
) -> str:
    if name == "simulation.get_metrics":
        metrics = result.get("metrics") or {}
        seed = result.get("random_seed")
        lines = [
            f"Сводка метрик симуляции (seed={_fmt(seed)}):",
        ]
        for key, title in (
            ("ai", "Ai"),
            ("ao", "Ao"),
            ("production_loss", "Потери продукции"),
            ("mtbf_minutes", "MTBF, мин"),
            ("mttr_minutes", "MTTR, мин"),
        ):
            value = metrics.get(key)
            if isinstance(value, dict) and value.get("mean") is not None:
                lines.append(
                    f"- {title}: среднее {_fmt(value.get('mean'))}, "
                    f"медиана {_fmt(value.get('median'))}"
                )
        pareto = metrics.get("failure_pareto") or []
        if pareto:
            lines.append("Топ вкладов в отказы (failure_pareto):")
            for row in pareto[:5]:
                key = str(row.get("key") or "")
                label = labels.get(key) or key
                lines.append(
                    f"  • {label}: count={_fmt(row.get('count'))}, "
                    f"share={_fmt(row.get('share'))}"
                )
        return "\n".join(lines)

    if name == "simulation.compare":
        lines = ["Сравнение сценария с базовой симуляцией:"]
        for key, title in (
            ("availability_delta", "Δ доступности"),
            ("production_loss_delta", "Δ потерь продукции"),
            ("maintenance_cost_delta", "Δ стоимости ТО"),
        ):
            if result.get(key) is not None:
                lines.append(f"- {title}: {_fmt(result.get(key))}")
        return "\n".join(lines)

    if name == "simulation.get_events":
        return (
            "Журнал событий симуляции: "
            f"записей={_fmt(result.get('count'))}, "
            f"offset={_fmt(result.get('offset'))}, "
            f"limit={_fmt(result.get('limit'))}."
        )

    if name == "failure_mode.search":
        return (
            _answer_failure_modes(
                [{"name": name, "ok": True, "result": result}],
                labels,
                "",
            )
            or ""
        )

    if name == "equipment.search":
        return (
            _answer_equipment(
                [{"name": name, "ok": True, "result": result}],
                "",
            )
            or ""
        )

    if name in {"maintenance.search", "reference.search"}:
        items = result.get("items") or []
        lines = [f"Результат `{name}`: найдено {_fmt(result.get('count'))}."]
        for item in items[:10]:
            label = (
                item.get("tag") or item.get("name") or item.get("id") or item
            )
            lines.append(f"- {label}")
        return "\n".join(lines)

    if name == "system.get":
        system = result.get("system") or {}
        version = result.get("version") or {}
        lines = ["Данные системы:"]
        if system:
            lines.append(f"- Система: {system.get('name')!r}")
        if version:
            lines.append(
                f"- Версия: v{version.get('version_number')} "
                f"({version.get('status')})"
            )
        return "\n".join(lines)

    if name == "scenario.get":
        return f"Сценарий: {result.get('name')!r}."

    return f"Данные инструмента `{name}` получены."


def _first_metrics(
    ok_results: list[dict[str, Any]],
) -> tuple[dict[str, Any], Any] | None:
    for entry in ok_results:
        if entry.get("name") != "simulation.get_metrics":
            continue
        result = entry.get("result") or {}
        metrics = result.get("metrics") or {}
        if isinstance(metrics, dict):
            return metrics, result.get("random_seed")
    return None


def _format_stat_block(
    stats: dict[str, Any],
    *,
    unit: str | None = None,
    indent: str = "- ",
) -> list[str]:
    unit_s = f" {unit}" if unit else ""
    lines: list[str] = []
    if stats.get("mean") is not None:
        lines.append(f"{indent}среднее: {_fmt(stats.get('mean'))}{unit_s}")
    if stats.get("median") is not None:
        lines.append(f"{indent}медиана: {_fmt(stats.get('median'))}{unit_s}")
    if stats.get("p5") is not None and stats.get("p95") is not None:
        lines.append(
            f"{indent}перцентили p5..p95: {_fmt(stats.get('p5'))} .. "
            f"{_fmt(stats.get('p95'))}{unit_s}"
        )
    if stats.get("ci_low") is not None and stats.get("ci_high") is not None:
        lines.append(
            f"{indent}ДИ среднего: {_fmt(stats.get('ci_low'))} … "
            f"{_fmt(stats.get('ci_high'))}{unit_s}"
        )
    if stats.get("sample_size") is not None:
        lines.append(
            f"{indent}число прогонов: {_fmt(stats.get('sample_size'))}"
        )
    return lines


def _equipment_labels(tool_results: list[dict[str, Any]]) -> dict[str, str]:
    labels: dict[str, str] = {}
    for entry in tool_results:
        if not entry.get("ok"):
            continue
        result = entry.get("result") or {}
        name = entry.get("name")
        if name == "equipment.search":
            for item in result.get("items") or []:
                eid = str(item.get("id") or "")
                if not eid:
                    continue
                tag = item.get("tag") or eid
                ename = item.get("name")
                labels[eid] = f"{tag}" + (f" ({ename})" if ename else "")
        if name == "simulation.get_metrics":
            metrics = result.get("metrics") or {}
            for row in metrics.get("equipment") or []:
                eid = str(row.get("equipment_id") or "")
                if eid and eid not in labels:
                    labels[eid] = eid
    return labels


def _looks_like_pump(label: str) -> bool:
    text = label.lower()
    if "насос" in text or "pump" in text:
        return True
    return bool(re.search(r"\bp-\d+", text, flags=re.I))


def _fmt(value: Any) -> str:
    """Format a tool number in a grounding-compatible way."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int | float):
        return _canon(value)
    return str(value)


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
