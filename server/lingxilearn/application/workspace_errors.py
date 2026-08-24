from __future__ import annotations


class WorkspaceDomainError(Exception):
    """Base error raised below the HTTP transport boundary."""

    status_code = 422

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class WorkspaceResourceNotFound(WorkspaceDomainError):
    status_code = 404


class WorkspaceForbidden(WorkspaceDomainError):
    status_code = 403


class WorkspacePayloadTooLarge(WorkspaceDomainError):
    status_code = 413
