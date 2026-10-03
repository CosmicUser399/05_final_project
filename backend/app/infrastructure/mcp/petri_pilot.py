"""Petri-Pilot MCP adapter (Streamable HTTP, whitelist only)."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.application.ports import PetriPilotResult
from app.application.ports import PetriPilotStatus
from app.config import Settings
from app.infrastructure.mcp.whitelist import PETRI_PILOT_WHITELIST

logger = logging.getLogger(__name__)

_CLIENT_INFO = {"name": "ai-reliability-modelling", "version": "0.1.0"}
_PROTOCOL_VERSION = "2024-11-05"


class PetriPilotMCPAdapter:
    """Call whitelisted Petri-Pilot tools over MCP Streamable HTTP."""

    def __init__(self, settings: Settings) -> None:
        """Bind URL, optional API key and timeout from settings."""
        self._url = settings.petri_pilot_mcp_url
        self._api_key = settings.petri_pilot_api_key
        self._timeout = settings.petri_pilot_timeout_seconds
        self._session_id: str | None = None
        self._rpc_id = 0
        self._initialized = False

    def validate(self, model_json: str) -> PetriPilotResult:
        """Call ``petri_validate``."""
        return self._call("petri_validate", {"model": model_json})

    def analyze(
        self,
        model_json: str,
        *,
        full: bool = False,
    ) -> PetriPilotResult:
        """Call ``petri_analyze``."""
        return self._call(
            "petri_analyze",
            {"model": model_json, "full": full},
        )

    def verify(
        self,
        model_json: str,
        properties: list[str],
        *,
        max_states: int | None = None,
    ) -> PetriPilotResult:
        """Call ``petri_verify``."""
        args: dict[str, Any] = {
            "model": model_json,
            "properties": json.dumps(properties),
        }
        if max_states is not None:
            args["max_states"] = str(max_states)
        return self._call("petri_verify", args)

    def invariants(self, model_json: str) -> PetriPilotResult:
        """Call ``petri_invariants``."""
        return self._call("petri_invariants", {"model": model_json})

    def simulate(
        self,
        model_json: str,
        *,
        transitions: list[str] | None = None,
    ) -> PetriPilotResult:
        """Call ``petri_simulate``."""
        args: dict[str, Any] = {"model": model_json}
        if transitions is not None:
            args["transitions"] = json.dumps(transitions)
        return self._call("petri_simulate", args)

    def conformance(
        self,
        model_json: str,
        log_json: str,
        *,
        include_traces: bool = True,
    ) -> PetriPilotResult:
        """Call ``petri_conformance``."""
        return self._call(
            "petri_conformance",
            {
                "model": model_json,
                "log": log_json,
                "include_traces": include_traces,
            },
        )

    def diff(self, model_a_json: str, model_b_json: str) -> PetriPilotResult:
        """Call ``petri_diff``."""
        return self._call(
            "petri_diff",
            {"model_a": model_a_json, "model_b": model_b_json},
        )

    def canonical(self, model_json: str) -> PetriPilotResult:
        """Call ``petri_canonical``."""
        return self._call("petri_canonical", {"model": model_json})

    def _call(self, tool: str, arguments: dict[str, Any]) -> PetriPilotResult:
        if tool not in PETRI_PILOT_WHITELIST:
            return PetriPilotResult(
                status=PetriPilotStatus.FAILURE,
                tool=tool,
                message=f"tool {tool!r} is not whitelisted",
            )
        if not self._url:
            return PetriPilotResult(
                status=PetriPilotStatus.EXTERNAL_ERROR,
                tool=tool,
                message="PETRI_PILOT_MCP_URL is not configured",
            )
        try:
            self._ensure_initialized()
            payload = self._rpc(
                "tools/call",
                {"name": tool, "arguments": arguments},
            )
        except httpx.TimeoutException:
            logger.warning("petri-pilot timeout tool=%s", tool)
            return PetriPilotResult(
                status=PetriPilotStatus.TIMEOUT,
                tool=tool,
                message="Petri-Pilot request timed out",
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "petri-pilot http error tool=%s err=%s",
                tool,
                type(exc).__name__,
            )
            return PetriPilotResult(
                status=PetriPilotStatus.EXTERNAL_ERROR,
                tool=tool,
                message="Petri-Pilot is unavailable",
            )
        except ValueError as exc:
            return PetriPilotResult(
                status=PetriPilotStatus.EXTERNAL_ERROR,
                tool=tool,
                message=str(exc),
            )
        return _normalize_tool_result(tool, payload)

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        self._rpc(
            "initialize",
            {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": _CLIENT_INFO,
            },
        )
        try:
            self._notify("notifications/initialized", {})
        except httpx.HTTPError:
            # Some servers ignore the notification; session may still work.
            logger.debug("petri-pilot initialized notify skipped")
        self._initialized = True

    def _require_url(self) -> str:
        if not self._url:
            msg = "PETRI_PILOT_MCP_URL is not configured"
            raise ValueError(msg)
        return self._url

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        headers = self._headers()
        body = {"jsonrpc": "2.0", "method": method, "params": params}
        url = self._require_url()
        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(url, headers=headers, json=body)
            self._capture_session(response)
            response.raise_for_status()

    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._rpc_id += 1
        body = {
            "jsonrpc": "2.0",
            "id": self._rpc_id,
            "method": method,
            "params": params,
        }
        headers = self._headers()
        url = self._require_url()
        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(url, headers=headers, json=body)
            self._capture_session(response)
            response.raise_for_status()
            data = _parse_json_response(response)
        if "error" in data:
            err = data["error"]
            msg = str(err.get("message", "MCP error"))
            raise ValueError(msg)
        result = data.get("result")
        if not isinstance(result, dict):
            raise ValueError("MCP result is not an object")
        return result

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._api_key is not None:
            secret = self._api_key.get_secret_value()
            if secret:
                headers["Authorization"] = f"Bearer {secret}"
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    def _capture_session(self, response: httpx.Response) -> None:
        session = response.headers.get("mcp-session-id")
        if session:
            self._session_id = session


def _parse_json_response(response: httpx.Response) -> dict[str, Any]:
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        return _parse_sse_jsonrpc(response.text)
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("MCP response is not an object")
    return data


def _parse_sse_jsonrpc(text: str) -> dict[str, Any]:
    """Extract the last JSON-RPC message from an SSE body."""
    last: dict[str, Any] | None = None
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        raw = line[5:].strip()
        if not raw or raw == "[DONE]":
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            last = payload
    if last is None:
        raise ValueError("empty SSE MCP response")
    return last


def _normalize_tool_result(
    tool: str,
    payload: dict[str, Any],
) -> PetriPilotResult:
    """Map MCP ``tools/call`` result to ``PetriPilotResult``."""
    if payload.get("isError"):
        message = _content_text(payload) or "Petri-Pilot tool error"
        status = PetriPilotStatus.FAILURE
        if "valid" in message.lower() or "invalid" in message.lower():
            status = PetriPilotStatus.VALIDATION_ERROR
        return PetriPilotResult(
            status=status,
            tool=tool,
            message=message,
            data={"raw": _safe_data(payload)},
        )
    data = _structured_or_json_content(payload)
    version = None
    if isinstance(data.get("version"), str):
        version = data["version"]
    return PetriPilotResult(
        status=PetriPilotStatus.SUCCESS,
        tool=tool,
        data=data,
        petri_pilot_version=version,
    )


def _structured_or_json_content(payload: dict[str, Any]) -> dict[str, Any]:
    structured = payload.get("structuredContent")
    if isinstance(structured, dict):
        return structured
    text = _content_text(payload)
    if text:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {"text": text}
        if isinstance(parsed, dict):
            return parsed
        return {"value": parsed}
    return _safe_data(payload)


def _content_text(payload: dict[str, Any]) -> str | None:
    content = payload.get("content")
    if not isinstance(content, list):
        return None
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
    if not parts:
        return None
    return "\n".join(parts)


def _safe_data(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop keys that might accidentally carry credentials."""
    blocked = {"authorization", "api_key", "token", "secret"}
    return {
        key: value
        for key, value in payload.items()
        if key.lower() not in blocked
    }
