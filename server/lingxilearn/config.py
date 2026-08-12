"""Application settings.

Every setting is read from the environment with the ``LINGXILEARN_`` prefix.
Secrets are :class:`SecretStr` so they never land in logs or tracebacks.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic.fields import AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict

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
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- content -----------------------------------------------------------
    packs_dir: Path = REPO_ROOT / "packs"
    var_dir: Path = REPO_ROOT / "var"

    # --- persistence -------------------------------------------------------
    # SQLite by default so a fresh clone runs with zero setup; point this at
    # PostgreSQL (postgresql+asyncpg://...) for the container deployment.
    database_url: str = "sqlite+aiosqlite:///./var/lingxilearn.sqlite3"
    # LingxiGraph's checkpointers are synchronous drivers, so they need their
    # own DSN in the driver's native form.
    checkpoint_url: str = ""

    # --- identity ----------------------------------------------------------
    # LingxiIdentity verifies OIDC discovery/JWKS and returns Principal. The
    # resource service never calls the Identity management API.
    # Defaults match the public LingxiLearn deployment. A tenant-specific
    # deployment should override both values together through the environment.
    oidc_issuer: str = "https://auth.lingxilearn.cn/oidc"
    oidc_audience: str = "https://lingxilearn.cn/api"
    oidc_timeout: float = 10.0
    insecure_dev_auth: bool = False
    dev_subject: str = "lingxilearn-dev"

    # --- tutor brain -------------------------------------------------------
    brain: BrainKind = "scripted"

    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: SecretStr = SecretStr("")
    llm_timeout: float = 45.0
    llm_temperature: float = 0.3

    # --- Agent Task runtime -----------------------------------------------
    # Agent tasks use one shared DeepSeek model. DS_API_KEY is intentionally
    # unprefixed because it is the repository-level credential requested by
    # the product contract; the alias keeps it out of public settings dumps.
    agent_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("DS_API_KEY", "LINGXILEARN_AGENT_API_KEY"),
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
    agent_visual_timeout: float = 240.0
    agent_web_timeout: float = 20.0
    # LingxiGraph 2.2.0 cache-first projection keeps each agent's stable
    # prompt/tool prefix intact so DeepSeek can use its native prompt cache.
    agent_cache_enabled: bool = True
    agent_cache_verify_mode: Literal["strict", "warn", "off"] = "strict"
    agent_max_html_bytes: int = 512 * 1024
    agent_task_dir: Path = REPO_ROOT / "var" / "agent_tasks"

    coze_bot_id: str = ""
    coze_base_url: str = "https://api.coze.cn"
    coze_token: SecretStr = SecretStr("")
    coze_timeout: float = 45.0

    # --- web ---------------------------------------------------------------
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    sse_heartbeat_seconds: float = 15.0
    max_artifact_bytes: int = 10 * 1024 * 1024

    log_level: str = "INFO"

    @field_validator("database_url")
    @classmethod
    def _known_async_driver(cls, value: str) -> str:
        allowed = ("sqlite+aiosqlite://", "postgresql+asyncpg://")
        if not value.startswith(allowed):
            raise ValueError(f"LINGXILEARN_DATABASE_URL must start with one of {allowed}")
        return value

    @property
    def resolved_database_url(self) -> str:
        """Anchor a relative SQLite path to the repo, not to the working directory.

        Without this, ``uvicorn`` started from ``server/`` and a script started
        from the repo root would quietly use two different databases.
        """
        prefix = "sqlite+aiosqlite:///"
        if not self.database_url.startswith(prefix):
            return self.database_url
        path = self.database_url[len(prefix) :]
        if path.startswith("/"):  # already absolute
            return self.database_url
        resolved = (REPO_ROOT / path.lstrip("./")).resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return f"{prefix}{resolved}"

    @property
    def resolved_checkpoint_url(self) -> str:
        """DSN for the LingxiGraph checkpointer, derived from the app DSN by default."""
        if self.checkpoint_url:
            return self.checkpoint_url
        if self.database_url.startswith("postgresql+asyncpg://"):
            return self.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
        path = self.resolved_database_url.split("///", 1)[-1]
        return str(Path(path).with_name("checkpoints.sqlite3"))

    @property
    def effective_brain(self) -> BrainKind:
        """Fall back to the deterministic brain when the chosen provider has no credential.

        This keeps the whole teaching loop runnable (and reproducible in CI)
        without an API key, instead of failing at the first coach turn.
        """
        if self.brain == "openai" and not self.llm_api_key.get_secret_value():
            return "scripted"
        if self.brain == "coze" and not (self.coze_token.get_secret_value() and self.coze_bot_id):
            return "scripted"
        return self.brain

    @property
    def agents_configured(self) -> bool:
        return bool(self.agent_api_key.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()
