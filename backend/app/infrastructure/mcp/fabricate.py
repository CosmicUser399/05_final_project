"""Fabricate MCP adapter (Streamable HTTP, whitelist only)."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

import httpx

from app.application.ports import ExternalCallStatus
from app.application.ports import FabricateCallResult
from app.config import Settings
from app.infrastructure.mcp.fabricate_whitelist import FABRICATE_WHITELIST

logger = logging.getLogger(__name__)

_CLIENT_INFO = {"name": "ai-reliability-modelling", "version": "0.1.0"}
_PROTOCOL_VERSION = "2024-11-05"


class FabricateMCPAdapter:
    """Call whitelisted Fabricate tools over MCP Streamable HTTP."""

    def __init__(self, settings: Settings) -> None:
        """Bind URL, API key and timeout from settings."""
        self._url = settings.fabricate_api_url
        self._api_key = settings.fabricate_api_key
        self._timeout = settings.fabricate_timeout_seconds
        self._session_id: str | None = None
        self._rpc_id = 0
        self._initialized = False

    def list_conversation_options(self) -> FabricateCallResult:
        """List models / modes before starting."""
        return self._call("list_conversation_options", {})

    def create_upload(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: str = "application/json",
    ) -> FabricateCallResult:
        """Upload schema/spec bytes (base64 in MCP args)."""
        return self._call(
            "create_upload",
            {
                "filename": filename,
                "content_base64": base64.b64encode(content).decode("ascii"),
                "content_type": content_type,
            },
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
        """Start async generation conversation."""
        args: dict[str, Any] = {
            "message": message,
            "upload_ids": upload_ids,
            "mode": mode,
            "approach": approach,
        }
        if model:
            args["model"] = model
        return self._call("start_conversation", args)

    def get_conversation_status(
        self,
        conversation_id: str,
    ) -> FabricateCallResult:
        """Poll conversation status."""
        return self._call(
            "get_conversation_status",
            {"conversation_id": conversation_id},
        )

    def get_conversation_result(
        self,
        conversation_id: str,
    ) -> FabricateCallResult:
        """Fetch conversation result metadata."""
        return self._call(
            "get_conversation_result",
            {"conversation_id": conversation_id},
        )

    def download_conversation_file(
        self,
        *,
        conversation_id: str,
        file_id: str,
    ) -> FabricateCallResult:
        """Download artifact; normalize to data.bytes when possible."""
        result = self._call(
            "download_conversation_file",
            {
                "conversation_id": conversation_id,
                "file_id": file_id,
            },
        )
        if result.status is not ExternalCallStatus.SUCCESS:
            return result
        data = dict(result.data)
        if "bytes" not in data and isinstance(data.get("content_base64"), str):
            try:
                data["bytes"] = base64.b64decode(data["content_base64"])
            except (ValueError, TypeError):
                return FabricateCallResult(
                    status=ExternalCallStatus.VALIDATION_ERROR,
                    tool=result.tool,
                    message="invalid content_base64 in download",
                )
        return FabricateCallResult(
            status=result.status,
            tool=result.tool,
            data=data,
            message=result.message,
        )

    def send_message(
        self,
        conversation_id: str,
        message: str,
        *,
        upload_ids: list[str] | None = None,
    ) -> FabricateCallResult:
        """Refine an existing conversation."""
        args: dict[str, Any] = {
            "conversation_id": conversation_id,
            "message": message,
        }
        if upload_ids:
            args["upload_ids"] = upload_ids
        return self._call("send_message", args)

    def stop_conversation(self, conversation_id: str) -> FabricateCallResult:
        """Cancel a running conversation."""
        return self._call(
            "stop_conversation",
            {"conversation_id": conversation_id},
        )

    def retry_conversation(self, conversation_id: str) -> FabricateCallResult:
        """Retry a failed turn in place."""
        return self._call(
            "retry_conversation",
            {"conversation_id": conversation_id},
        )

    def _call(
        self,
        tool: str,
        arguments: dict[str, Any],
    ) -> FabricateCallResult:
        if tool not in FABRICATE_WHITELIST:
            return FabricateCallResult(
                status=ExternalCallStatus.FAILURE,
                tool=tool,
                message=f"tool {tool!r} is not whitelisted",
            )
        if not self._url:
            return FabricateCallResult(
                status=ExternalCallStatus.EXTERNAL_ERROR,
                tool=tool,
                message="FABRICATE_API_URL is not configured",
            )
        try:
            self._ensure_initialized()
            payload = self._rpc(
                "tools/call",
                {"name": tool, "arguments": arguments},
            )
        except httpx.TimeoutException:
            logger.warning("fabricate timeout tool=%s", tool)
            return FabricateCallResult(
                status=ExternalCallStatus.TIMEOUT,
                tool=tool,
                message="Fabricate request timed out",
            )
        except httpx.HTTPError:
            logger.warning("fabricate http error tool=%s", tool)
            return FabricateCallResult(
                status=ExternalCallStatus.EXTERNAL_ERROR,
                tool=tool,
                message="Fabricate is unavailable",
            )
        except ValueError as exc:
            return FabricateCallResult(
                status=ExternalCallStatus.EXTERNAL_ERROR,
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
            logger.debug("fabricate initialized notify skipped")
        self._initialized = True

    def _require_url(self) -> str:
        if not self._url:
            msg = "FABRICATE_API_URL is not configured"
            raise ValueError(msg)
        return self._url

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        headers = self._headers()
        body = {"jsonrpc": "2.0", "method": method, "params": params}
        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(
                self._require_url(),
                headers=headers,
                json=body,
            )
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
        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(
                self._require_url(),
                headers=headers,
                json=body,
            )
            self._capture_session(response)
            response.raise_for_status()
            data = _parse_json_response(response)
        if "error" in data:
            err = data["error"]
            raise ValueError(str(err.get("message", "MCP error")))
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
) -> FabricateCallResult:
    if payload.get("isError"):
        message = _content_text(payload) or "Fabricate tool error"
        return FabricateCallResult(
            status=ExternalCallStatus.FAILURE,
            tool=tool,
            message=message,
            data=_safe_data(payload),
        )
    data = _structured_or_json_content(payload)
    return FabricateCallResult(
        status=ExternalCallStatus.SUCCESS,
        tool=tool,
        data=data,
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
    return "\n".join(parts) if parts else None


def _safe_data(payload: dict[str, Any]) -> dict[str, Any]:
    blocked = {"authorization", "api_key", "token", "secret"}
    return {
        key: value
        for key, value in payload.items()
        if key.lower() not in blocked
    }
