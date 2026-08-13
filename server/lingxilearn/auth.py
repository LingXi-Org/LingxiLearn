"""Authentication boundary for the LingxiLearn resource service.

Production requests use LingxiIdentity's HttpOnly BFF session. LingxiLearn
forwards the opaque cookie to ``/api/v1/me`` and trusts only the BFF response;
the browser never receives or stores an OIDC bearer token.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import HTTPException, Request
from lingxi_identity import Principal  # type: ignore[import-untyped]

from .config import Settings


def _authentication_error(detail: str = "invalid_token") -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=detail,
    )


@dataclass(slots=True)
class Authenticator:
    """Resolve an opaque LingxiIdentity BFF cookie to a verified principal."""

    settings: Settings
    client: httpx.AsyncClient

    async def authenticate(self, cookie: str | None) -> Principal:
        if not cookie:
            if self.settings.insecure_dev_auth:
                return Principal(subject=self.settings.dev_subject, issuer="lingxilearn-dev")
            raise _authentication_error("authentication_required")
        try:
            response = await self.client.get(
                f"{self.settings.identity_bff_url.rstrip('/')}/api/v1/me",
                headers={"Cookie": cookie, "Accept": "application/json"},
            )
        except (httpx.HTTPError, TimeoutError, OSError) as exc:
            raise HTTPException(
                status_code=503,
                detail="identity_provider_unavailable",
            ) from exc
        if response.status_code == 401:
            raise _authentication_error("authentication_required")
        if not response.is_success:
            raise HTTPException(status_code=503, detail="identity_provider_unavailable")
        body = response.json()
        principal: dict[str, Any] = body.get("principal") or {}
        subject = principal.get("subject")
        if not subject:
            raise _authentication_error("invalid_identity")
        return Principal(
            subject=str(subject),
            tenant_id=principal.get("tenant_id"),
            roles=frozenset(str(item) for item in principal.get("roles") or []),
            permissions=frozenset(str(item) for item in principal.get("permissions") or []),
            issuer=principal.get("issuer"),
            audience=frozenset(str(item) for item in principal.get("audience") or []),
        )

    async def aclose(self) -> None:
        await self.client.aclose()


def build_authenticator(settings: Settings) -> Authenticator:
    """Create the BFF client once and reuse its connection pool."""

    if not settings.identity_bff_url and not settings.insecure_dev_auth:
        raise RuntimeError("LINGXILEARN_IDENTITY_BFF_URL is required")
    return Authenticator(
        settings=settings,
        client=httpx.AsyncClient(timeout=settings.identity_bff_timeout, follow_redirects=False),
    )


async def get_principal(request: Request) -> Principal:
    """FastAPI dependency used by every persistent user-data endpoint."""

    authenticator: Authenticator | None = getattr(request.app.state, "identity", None)
    if authenticator is None:
        raise HTTPException(status_code=503, detail="identity_unavailable")
    return await authenticator.authenticate(request.headers.get("cookie"))
