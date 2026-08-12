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

from lingxigraph import AIMessageChunk, ToolCallChunk
from lingxigraph.integrations import OpenAICompatChatModel
from lingxigraph.integrations._http import should_retry_status, sleep_before_retry
from lingxigraph.runtime import get_runtime


class TracedOpenAICompatChatModel(OpenAICompatChatModel):
    """Keep reasoning deltas available to LingxiGraph's message stream."""

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
                            additional["reasoning_content"] = reasoning
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
