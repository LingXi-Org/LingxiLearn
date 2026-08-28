"""Coze tutor brain.

Coze bots are remote agents addressed by ``bot_id`` rather than model configs,
but LingxiGraph's ``CozeChatModel`` implements the same ``ChatModel`` protocol
as the OpenAI adapter — so everything above the constructor is shared with
:mod:`lingxilearn.brains.llm`, including its strict JSON contract.
"""

from __future__ import annotations

from lingxigraph.integrations import AsyncCozeClient, CozeChatModel

from ..config import Settings
from .llm import LlmBrain


class CozeBrain(LlmBrain):
    name = "coze"

    def __init__(self, settings: Settings, *, user_id: str = "lingxilearn") -> None:
        self._client = AsyncCozeClient(
            settings.coze_token.get_secret_value(),
            base_url=settings.coze_base_url,
            timeout=settings.coze_timeout,
        )
        super().__init__(CozeChatModel(settings.coze_bot_id, client=self._client, user_id=user_id))

    async def aclose(self) -> None:
        closer = getattr(self._client, "aclose", None) or getattr(self._client, "close", None)
        if callable(closer):
            result = closer()
            if hasattr(result, "__await__"):
                await result
