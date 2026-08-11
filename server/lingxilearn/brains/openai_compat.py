"""OpenAI-compatible tutor brain.

Works against any endpoint speaking the OpenAI chat-completions API — OpenAI
itself, DeepSeek, Qwen/DashScope compat, Moonshot, vLLM, Ollama — by pointing
``LINGXILEARN_LLM_BASE_URL`` at it.  Swapping provider is three environment
variables, not a code change.

Note ``OpenAICompatChatModel`` takes no ``temperature`` argument; per-request
options go through ``default_options``.
"""

from __future__ import annotations

from lingxigraph.integrations import OpenAICompatChatModel

from ..config import Settings
from .llm import LlmBrain


class OpenAICompatBrain(LlmBrain):
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        model = OpenAICompatChatModel(
            settings.llm_model,
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key.get_secret_value() or None,
            timeout=settings.llm_timeout,
            default_options={"temperature": settings.llm_temperature},
        )
        super().__init__(model)
