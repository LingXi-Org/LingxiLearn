"""Application settings.

Every setting is read from the environment with the ``LINGXILEARN_`` prefix.
Secrets are :class:`SecretStr` so they never land in logs or tracebacks.
"""

from __future__ import annotations

import asyncio
import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

if sys.platform == "win32":
    selector_policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
    if selector_policy is not None:
        asyncio.set_event_loop_policy(selector_policy())

_source_root = Path(__file__).resolve().parents[2]
_installed_root = Path(__file__).resolve().parents[1]
# In the source checkout the package lives below ``server/``; in the Docker
# image it is copied directly below ``/app``.  Resolve the root from the
# mounted/runtime assets instead of assuming one directory layout.
REPO_ROOT = _source_root if (_source_root / "skills").is_dir() else _installed_root

BrainKind = Literal["scripted", "openai", "coze"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LINGXILEARN_",
        # Resolve the checkout's root environment file regardless of whether
        # uvicorn is started from the repository root, ``server/``, or a
        # container working directory.
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- content -----------------------------------------------------------
    packs_dir: Path = REPO_ROOT / "packs"
    var_dir: Path = REPO_ROOT / "var"

    # --- persistence -------------------------------------------------------
    database_url: str = ""
    # LingxiGraph's checkpointers are synchronous drivers, so they need their
    # own DSN in the driver's native form.
    checkpoint_url: str = ""

    # --- identity ----------------------------------------------------------
    # LingxiIdentity owns OIDC, account operations and the encrypted session.
    # This resource service only forwards the opaque browser cookie to the BFF
    # and consumes its verified Principal response.
    identity_bff_url: str = ""
    identity_bff_timeout: float = 10.0
    # Raw orchestration diagnostics are an explicit operator capability. Keep
    # this disabled in normal deployments; it is intended for local/internal
    # debugging only and is never inferred from a learner session.
    runtime_debug_enabled: bool = False

    # --- tutor brain -------------------------------------------------------
    brain: BrainKind = "scripted"

    llm_model: str = "deepseek-v4-flash"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: SecretStr = SecretStr("")
    llm_timeout: float = 45.0
    llm_temperature: float = 0.3

    # --- Agent Task runtime -----------------------------------------------
    # Agent tasks use one shared DeepSeek model. DS_API_KEY is intentionally
    # unprefixed because it is the repository-level credential requested by
    # the product contract.
    agent_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="DS_API_KEY",
        repr=False,
    )
    agent_model: str = "deepseek-v4-flash"
    agent_base_url: str = "https://api.deepseek.com"
    agent_timeout: float = 90.0
    # Intent and visual generation normally finish within the shared timeout,
    # while lecture-hook may perform several bounded research calls first.
    agent_lecture_timeout: float = 180.0
    # Deck generation is optimized to finish well below this ceiling. Keep a
    # separate guard so strict validation repair can complete without also
    # relaxing the single-page visual explainer timeout.
    agent_deck_timeout: float = 360.0
    # A deck requires several progressive-disclosure and artifact-writing
    # turns. Keep this independent from the parent graph limit so a verbose
    # model cannot exhaust the child graph at the old hard-coded limit.
    agent_deck_recursion_limit: int = 40
    agent_visual_timeout: float = 240.0
    # A small production VM should queue expensive graph executions instead
    # of allowing every request to retain a full model context.
    agent_concurrency: int = 1
    agent_parallel_dispatch: bool = True
    agent_web_timeout: float = 20.0
    # LingxiGraph 2.2.0 cache-first projection keeps each agent's stable
    # prompt/tool prefix intact so DeepSeek can use its native prompt cache.
    agent_cache_enabled: bool = True
    agent_cache_verify_mode: Literal["strict", "warn", "off"] = "strict"
    # Retry blocks are opt-in; non-idempotent Agent primitives run once.
    agent_retry_max_tries: int = 1
    agent_retry_wait_seconds: float = 0.0
    agent_max_html_bytes: int = 512 * 1024
    agent_task_dir: Path = REPO_ROOT / "var" / "agent_tasks"

    coze_bot_id: str = ""
    coze_base_url: str = "https://api.coze.cn"
    coze_token: SecretStr = SecretStr("")
    coze_timeout: float = 45.0

    # --- web ---------------------------------------------------------------
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    sse_heartbeat_seconds: float = 15.0
    max_artifact_bytes: int = 10 * 1024 * 1024

    # Keep the database pool below the memory budget.  The API never holds a
    # connection for the duration of an LLM/graph run.
    db_pool_size: int = 3
    db_max_overflow: int = 1

    log_level: str = "INFO"

    @field_validator("database_url")
    @classmethod
    def _known_async_driver(cls, value: str) -> str:
        if not value:
            return value
        allowed = ("postgresql+asyncpg://", "postgresql+psycopg://")
        if not value.startswith(allowed):
            raise ValueError(f"LINGXILEARN_DATABASE_URL must start with one of {allowed}")
        return value

    @property
    def resolved_database_url(self) -> str:
        return self.database_url

    @property
    def resolved_checkpoint_url(self) -> str:
        """DSN for the LingxiGraph checkpointer, derived from the app DSN by default."""
        if self.checkpoint_url:
            return self.checkpoint_url
        for prefix in ("postgresql+asyncpg://", "postgresql+psycopg://"):
            if self.database_url.startswith(prefix):
                return self.database_url.replace(prefix, "postgresql://", 1)
        return ""

    @property
    def effective_brain(self) -> BrainKind:
        return self.brain

    @property
    def agents_configured(self) -> bool:
        return bool(self.agent_api_key.get_secret_value())

    def validate_runtime(self) -> None:
        """Validate the complete production composition before opening resources."""

        errors: list[dict[str, str]] = []
        if not self.database_url:
            errors.append({"field": "LINGXILEARN_DATABASE_URL", "code": "required"})
        elif not self.database_url.startswith(("postgresql+asyncpg://", "postgresql+psycopg://")):
            errors.append({"field": "LINGXILEARN_DATABASE_URL", "code": "postgresql_required"})
        if not self.identity_bff_url.strip():
            errors.append({"field": "LINGXILEARN_IDENTITY_BFF_URL", "code": "required"})
        if self.brain == "openai" and not self.llm_api_key.get_secret_value():
            errors.append({"field": "LINGXILEARN_LLM_API_KEY", "code": "required_for_openai"})
        if self.brain == "coze":
            if not self.coze_token.get_secret_value():
                errors.append({"field": "LINGXILEARN_COZE_TOKEN", "code": "required_for_coze"})
            if not self.coze_bot_id.strip():
                errors.append({"field": "LINGXILEARN_COZE_BOT_ID", "code": "required_for_coze"})
        if not self.agent_api_key.get_secret_value():
            errors.append({"field": "DS_API_KEY", "code": "required_for_agent_tasks"})
        if not self.resolved_checkpoint_url:
            errors.append({"field": "LINGXILEARN_CHECKPOINT_URL", "code": "postgresql_required"})
        if errors:
            raise RuntimeError(
                json.dumps(
                    {"code": "configuration.invalid", "errors": errors},
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
