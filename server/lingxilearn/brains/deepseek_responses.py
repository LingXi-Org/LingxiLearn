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
                inputs.append({"role": "assistant" if message.type == "ai" else "user", "content": text})
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

    async def agenerate(self, messages: Sequence[AnyMessage], **_: Any) -> AIMessage:
        response = await self._client.post("/responses", json=self._payload(messages))
        response.raise_for_status()
        payload = response.json()
        return AIMessage(
            self._output_text(payload),
            usage=dict(payload.get("usage") or {}),
            response_metadata={"model": payload.get("model"), "provider": self.provider_id},
        )

    async def astream(self, messages: Sequence[AnyMessage], **kwargs: Any) -> AsyncIterator[AIMessageChunk]:
        response = await self.agenerate(messages, **kwargs)
        yield AIMessageChunk(response.content, usage=response.usage, response_metadata=response.response_metadata)

    async def aclose(self) -> None:
        await self._client.aclose()
