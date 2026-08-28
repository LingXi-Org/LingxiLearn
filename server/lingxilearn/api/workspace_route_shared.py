"""Workspace HTTP composition helpers."""

from __future__ import annotations

from typing import NoReturn

from fastapi import HTTPException, Request

from ..application.workspace_errors import WorkspaceDomainError
from ..domain.workspace import Workspace
from ..learner import LearnerContext
from .dependencies import services_of


def _raise_http(error: WorkspaceDomainError) -> NoReturn:
    raise HTTPException(status_code=error.status_code, detail=error.code) from error


async def _workspace(request: Request, context: LearnerContext) -> Workspace:
    return await services_of(request).workspaces.resolve(context.learner_id)


async def _workspace_for_id(
    request: Request, workspace_id: str, context: LearnerContext
) -> Workspace:
    try:
        return await services_of(request).workspaces.resolve(context.learner_id, workspace_id)
    except WorkspaceDomainError as error:
        _raise_http(error)
