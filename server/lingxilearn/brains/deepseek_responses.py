"""DeepSeek Responses API adapter with native web search."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

import httpx
from lingxigraph import AIMessage, AIMessageChunk, AnyMessage


class DeepSeekResponsesModel:
    """Minimal LingxiGraph ChatModel adapter for DeepSeek ``/responses``."""

    provider_id = "deepseek-responses"

    def __init__(self, model: str, *, base_url: str, api_key: str, timeout: float) -> None:
        self.model = model
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    @staticmethod
    def _text(message: AnyMessage) -> str:
        content = getattr(message, "content", "")
        return content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)

    def _payload(self, messages: Sequence[AnyMessage]) -> dict[str, Any]:
        instructions: list[str] = []
        inputs: list[dict[str, str]] = []
        for message in messages:
            text = self._text(message)
            if message.type == "system":
                instructions.append(text)
            else:
                inputs.append(
                    {"role": "assistant" if message.type == "ai" else "user", "content": text}
                )
        payload: dict[str, Any] = {
            "model": self.model,
            "input": inputs,
            "tools": [{"type": "web_search"}],
            "tool_choice": "auto",
        }
        if instructions:
            payload["instructions"] = "\n\n".join(instructions)
        return payload

    @staticmethod
    def _output_text(payload: Mapping[str, Any]) -> str:
        if isinstance(payload.get("output_text"), str):
            return str(payload["output_text"])
        parts: list[str] = []
        for item in payload.get("output", ()) or ():
            if isinstance(item, Mapping):
                for content in item.get("content", ()) or ():
                    if isinstance(content, Mapping) and isinstance(content.get("text"), str):
                        parts.append(str(content["text"]))
        return "".join(parts)

    @staticmethod
    def _output_reasoning(payload: Mapping[str, Any]) -> str:
        parts: list[str] = []
        for item in payload.get("output", ()) or ():
            if not isinstance(item, Mapping):
                continue
            for key in ("reasoning_content", "reasoning", "thinking"):
                value = item.get(key)
                if isinstance(value, str):
                    parts.append(value)
            for content in item.get("content", ()) or ():
                if isinstance(content, Mapping) and str(content.get("type", "")).startswith(
                    "reasoning"
                ):
                    if isinstance(content.get("text"), str):
                        parts.append(str(content["text"]))
        return "".join(parts)

    async def agenerate(self, messages: Sequence[AnyMessage], **_: Any) -> AIMessage:
        response = await self._client.post("/responses", json=self._payload(messages))
        response.raise_for_status()
        payload = response.json()
        reasoning = self._output_reasoning(payload)
        return AIMessage(
            self._output_text(payload),
            usage=dict(payload.get("usage") or {}),
            additional_kwargs={"reasoning_content": reasoning} if reasoning else {},
            response_metadata={"model": payload.get("model"), "provider": self.provider_id},
        )

    async def astream(
        self, messages: Sequence[AnyMessage], **kwargs: Any
    ) -> AsyncIterator[AIMessageChunk]:
        payload = self._payload(messages)
        payload["stream"] = True
        async with self._client.stream("POST", "/responses", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw == "[DONE]":
                    return
                event = json.loads(raw)
                event_type = str(event.get("type") or "")
                value = event.get("delta") or event.get("text") or ""
                additional: dict[str, Any] = {}
                if "reasoning" in event_type or "thinking" in event_type:
                    if value:
                        additional["reasoning_content"] = str(value)
                    value = ""
                usage = dict(
                    event.get("usage")
                    or (event.get("response") or {}).get("usage")
                    or {}
                )
                if value or additional or usage:
                    yield AIMessageChunk(
                        str(value),
                        usage=usage,
                        additional_kwargs=additional,
                        response_metadata={
                            "model": event.get("model"),
                            "provider": self.provider_id,
                        },
                    )

    async def aclose(self) -> None:
        await self._client.aclose()
