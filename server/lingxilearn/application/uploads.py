from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from .workspace_errors import WorkspaceDomainError, WorkspaceResourceNotFound

# Local upload compatibility state is shared by Files and Knowledge. Keeping
# one application-owned registry prevents domain routers importing each other.
upload_sessions: dict[str, dict[str, Any]] = {}


def multipart_part_urls(
    upload_id: str,
    item: dict[str, Any] | None,
    learner_id: str,
    upload_token: str | None,
    body: dict[str, Any],
    public_origin: str,
) -> dict[str, Any]:
    if item is None or item["learner_id"] != learner_id or upload_token != item["token"]:
        raise WorkspaceResourceNotFound("resource_not_found")
    numbers = body.get("partNumbers")
    if not isinstance(numbers, list) or not numbers or len(numbers) > 100:
        raise WorkspaceDomainError("invalid_part_numbers")
    try:
        part_numbers = sorted({int(number) for number in numbers})
    except (TypeError, ValueError) as exc:
        raise WorkspaceDomainError("invalid_part_numbers") from exc
    if any(number < 1 for number in part_numbers):
        raise WorkspaceDomainError("invalid_part_numbers")
    expires = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    return {
        "data": {
            "parts": [
                {
                    "partNumber": number,
                    "url": f"{public_origin}/api/v2/uploads/{upload_id}/parts/{number}?token={item['token']}",
                    "headers": {},
                    "expiresAt": expires,
                }
                for number in part_numbers
            ]
        }
    }
