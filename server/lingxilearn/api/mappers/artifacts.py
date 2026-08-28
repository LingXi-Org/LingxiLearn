"""Artifact DTO mapping."""

from ...domain.artifact import Artifact


def artifact_response(artifact: Artifact) -> dict[str, object]:
    return {
        "id": artifact.id,
        "workspaceId": "lingxi",
        "name": artifact.name,
        "mimeType": artifact.mime_type,
        "size": artifact.size,
        "source": artifact.source,
        "taskId": artifact.task_id,
        "kind": artifact.kind,
        "createdAt": artifact.created_at.isoformat() if artifact.created_at else None,
        "updatedAt": artifact.updated_at.isoformat() if artifact.updated_at else None,
    }
