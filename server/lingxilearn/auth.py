"""Authentication boundary for the LingxiLearn resource service.

The service trusts only the :class:`lingxi_identity.Principal` returned by the
LingxiIdentity OIDC verifier.  There is deliberately no client supplied
learner id or subject fallback here.  The explicit development switch is the
only exception, and it always resolves to the configured fixed subject.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx
from fastapi import HTTPException, Request
from lingxi_identity import OidcVerifier, Principal  # type: ignore[import-untyped]

from .config import Settings

logger = logging.getLogger(__name__)


def _authentication_error(detail: str = "invalid_token") -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


@dataclass(slots=True)
class Authenticator:
    """Verify bearer tokens or, only in explicit local development, use one subject."""

    settings: Settings
    verifier: OidcVerifier | None = None

    async def authenticate(self, authorization: str | None) -> Principal:
        if not authorization:
            if self.settings.insecure_dev_auth:
                return Principal(
                    subject=self.settings.dev_subject,
                    issuer=self.settings.oidc_issuer or "lingxilearn-dev",
                    audience=frozenset(
                        {self.settings.oidc_audience}
                        if self.settings.oidc_audience
                        else set()
                    ),
                )
            raise _authentication_error("authentication_required")

        scheme, separator, token = authorization.partition(" ")
        if not separator or scheme.lower() != "bearer" or not token.strip():
            raise _authentication_error()
        if self.verifier is None:
            # A token cannot be accepted when OIDC is not configured.  The
            # dev switch only supplies the fixed identity for requests that do
            # not carry a token; it is never a client-controlled identity.
            raise _authentication_error()

        try:
            # OIDC discovery/JWKS refresh is synchronous in the SDK.  Keep it
            # off the asyncio event loop, including the first request.
            return await asyncio.to_thread(self.verifier.verify, token.strip())
        except (httpx.HTTPError, TimeoutError, OSError) as exc:
            raise HTTPException(
                status_code=503,
                detail="identity_provider_unavailable",
            ) from exc
        except Exception as exc:  # noqa: BLE001 - all verifier failures are 401
            # Keep the token itself out of logs, but expose the verifier
            # failure class so a deployment can distinguish issuer, audience,
            # expiry, and signature problems from a missing Authorization
            # header.
            logger.warning(
                "OIDC bearer rejected: %s (issuer=%s audience=%s)",
                type(exc).__name__,
                self.settings.oidc_issuer,
                self.settings.oidc_audience,
            )
            raise _authentication_error() from exc


def build_authenticator(settings: Settings) -> Authenticator:
    """Construct the verifier at startup so production misconfiguration fails fast."""

    has_oidc = bool(settings.oidc_issuer and settings.oidc_audience)
    if not has_oidc and not settings.insecure_dev_auth:
        raise RuntimeError(
            "LINGXILEARN_OIDC_ISSUER and LINGXILEARN_OIDC_AUDIENCE are required "
            "unless LINGXILEARN_INSECURE_DEV_AUTH=true"
        )
    verifier = (
        OidcVerifier(
            issuer=settings.oidc_issuer,
            audience=settings.oidc_audience,
            timeout=settings.oidc_timeout,
        )
        if has_oidc
        else None
    )
    return Authenticator(settings=settings, verifier=verifier)


async def get_principal(request: Request) -> Principal:
    """FastAPI dependency used by every persistent user-data endpoint."""

    authenticator: Authenticator | None = getattr(request.app.state, "identity", None)
    if authenticator is None:
        raise HTTPException(status_code=503, detail="identity_unavailable")
    return await authenticator.authenticate(request.headers.get("authorization"))
