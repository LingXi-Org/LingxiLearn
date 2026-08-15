"""OpenAI-compatible model adapter that preserves reasoning stream deltas.

LingxiGraph already streams ``AIMessageChunk`` values, but the bundled
OpenAI-compatible adapter only kept normal content and tool-call deltas.  This
small subclass keeps the upstream transport and cache integration while adding
provider fields such as DeepSeek's ``reasoning_content`` to
``AIMessageChunk.additional_kwargs``.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from typing import Any
from uuid import uuid4

import httpx
import lingxigraph.integrations.openai_compat as _compat_module
from lingxigraph import AIMessage, AIMessageChunk, ToolCallChunk
from lingxigraph.integrations import OpenAICompatChatModel
from lingxigraph.integrations._http import should_retry_status, sleep_before_retry
from lingxigraph.integrations.openai_compat import _tool_calls
from lingxigraph.runtime import get_runtime


class TracedOpenAICompatChatModel(OpenAICompatChatModel):
    """Keep reasoning deltas available to LingxiGraph's message stream."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Defer httpx's native TLS initialisation until a request is made.
        original = _compat_module.httpx.AsyncClient
        _compat_module.httpx.AsyncClient = _LazyAsyncClient  # type: ignore[assignment,misc]
        try:
            super().__init__(*args, **kwargs)
        finally:
            _compat_module.httpx.AsyncClient = original  # type: ignore[assignment,misc]

    async def aclose(self) -> None:
        client = getattr(self, "_client", None)
        if client is not None:
            await client.aclose()

    def _payload(
        self,
        messages: Sequence[Any],
        tools: Sequence[Any] | None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Keep DeepSeek reasoning content across tool-call turns."""

        payload = super()._payload(messages, tools, **kwargs)
        encoded_messages = payload.get("messages") or []
        for message, encoded in zip(messages, encoded_messages, strict=False):
            if getattr(message, "type", "") != "ai":
                continue
            additional = getattr(message, "additional_kwargs", {}) or {}
            reasoning = (
                (
                    additional.get("reasoning_content")
                    or additional.get("reasoning")
                    or additional.get("thinking")
                )
                if isinstance(additional, dict)
                else None
            )
            if reasoning:
                encoded["reasoning_content"] = str(reasoning)
        return payload

    async def _agenerate_raw(
        self,
        messages: Sequence[Any],
        *,
        tools: Sequence[Any] | None = None,
        **kwargs: Any,
    ) -> AIMessage:
        """Preserve reasoning metadata on non-streaming Agent invocations too."""

        response = await self._post(self._payload(messages, tools, **kwargs))
        payload = response.json()
        choice = payload["choices"][0]
        message = choice["message"]
        reasoning = (
            message.get("reasoning_content")
            or message.get("reasoning")
            or message.get("thinking")
            or ""
        )
        return AIMessage(
            message.get("content") or "",
            tool_calls=_tool_calls(message.get("tool_calls", ())),
            usage=dict(payload.get("usage") or {}),
            additional_kwargs={"reasoning_content": str(reasoning)} if reasoning else {},
            response_metadata={
                "finish_reason": choice.get("finish_reason"),
                "model": payload.get("model"),
            },
        )

    async def _astream_raw(
        self,
        messages: Sequence[Any],
        *,
        tools: Sequence[Any] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[AIMessageChunk]:
        payload = self._payload(messages, tools, **kwargs)
        payload["stream"] = True
        payload.setdefault("stream_options", {"include_usage": True})
        emitted = False
        operation_key = str(uuid4())
        reasoning_parts: list[str] = []
        for attempt in range(self.max_retries + 1):
            try:
                async with self._client.stream(
                    "POST",
                    "/chat/completions",
                    json=payload,
                    headers=self._request_headers(operation_key),
                ) as response:
                    if (
                        should_retry_status(response.status_code)
                        and attempt < self.max_retries
                        and not emitted
                    ):
                        await response.aread()
                        await sleep_before_retry(
                            attempt + 1, response.headers, base=self.retry_base
                        )
                        continue
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        try:
                            get_runtime().raise_if_cancelled()
                        except RuntimeError:
                            pass
                        if not line.startswith("data:"):
                            continue
                        raw = line[5:].strip()
                        if raw == "[DONE]":
                            return
                        event = json.loads(raw)
                        choices = event.get("choices", ())
                        choice = choices[0] if choices else {}
                        delta = choice.get("delta", {}) or {}
                        chunks = tuple(
                            ToolCallChunk(
                                name=item.get("function", {}).get("name"),
                                args=item.get("function", {}).get("arguments", ""),
                                id=item.get("id"),
                                index=int(item.get("index", 0)),
                            )
                            for item in delta.get("tool_calls", ())
                        )
                        additional: dict[str, Any] = {}
                        reasoning = (
                            delta.get("reasoning_content")
                            or delta.get("reasoning")
                            or delta.get("thinking")
                        )
                        if reasoning:
                            reasoning_parts.append(str(reasoning))
                            additional["reasoning_content"] = reasoning
                        if choice.get("finish_reason") and reasoning_parts:
                            # LingxiGraph merges the final chunk into the
                            # assistant message used for the next tool turn.
                            # Carry the complete DeepSeek reasoning there or
                            # its API rejects the follow-up request with 400.
                            additional["reasoning_content"] = "".join(reasoning_parts)
                            additional["_reasoning_replay"] = True
                        usage = dict(event.get("usage") or {})
                        value = AIMessageChunk(
                            delta.get("content") or "",
                            id=event.get("id"),
                            tool_call_chunks=chunks,
                            usage=usage,
                            additional_kwargs=additional,
                            response_metadata={
                                "model": event.get("model"),
                                "finish_reason": choice.get("finish_reason"),
                            },
                        )
                        if (
                            value.content
                            or value.tool_call_chunks
                            or value.usage
                            or value.additional_kwargs
                            or choice.get("finish_reason")
                        ):
                            emitted = True
                            yield value
                    return
            except Exception as exc:
                # Preserve the upstream retry policy for transport failures while
                # allowing provider JSON/schema errors to surface immediately.
                import httpx

                if not isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
                    raise
                if emitted or attempt >= self.max_retries:
                    raise
                await sleep_before_retry(attempt + 1, base=self.retry_base)


__all__ = ["TracedOpenAICompatChatModel"]


class _LazyAsyncClient:
    def __init__(self, **kwargs: Any) -> None:
        self._kwargs = kwargs
        self._client: httpx.AsyncClient | None = None

    def _get(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(**self._kwargs)
        return self._client

    async def post(self, *args: Any, **kwargs: Any) -> httpx.Response:
        return await self._get().post(*args, **kwargs)

    def stream(self, *args: Any, **kwargs: Any) -> Any:
        return self._get().stream(*args, **kwargs)

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
