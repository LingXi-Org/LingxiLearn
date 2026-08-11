"""The evidence ledger — the backbone of "可追溯学习证据".

Tool output, knowledge citations, learner actions and simulator frames all
land here with a stable id.  Teaching claims reference those ids; the UI
resolves an id back to a frame, a citation or a simulator step.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .contracts import Evidence, EvidenceKind


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class Ledger:
    """Append-only evidence store scoped to one graph run.

    Ids are positional (``ev_0007``) so they stay readable in the transcript,
    and each entry carries a content digest so a replay cannot silently
    substitute a different value behind the same id.
    """

    def __init__(self, existing: list[dict[str, Any]] | None = None) -> None:
        self._entries: list[Evidence] = [
            Evidence(
                id=item["id"],
                kind=item["kind"],
                source=item["source"],
                summary=item.get("summary", ""),
                locator=item.get("locator", {}),
                value=item.get("value"),
                digest=item.get("digest", ""),
            )
            for item in (existing or [])
        ]
        self._added: list[Evidence] = []

    def add(
        self,
        *,
        kind: EvidenceKind,
        source: str,
        summary: str,
        locator: dict[str, Any] | None = None,
        value: Any = None,
    ) -> Evidence:
        digest = _digest({"source": source, "locator": locator or {}, "value": value})
        for entry in self._entries:
            if entry.source == source and entry.digest == digest:
                return entry  # idempotent across node re-runs after an interrupt
        item = Evidence(
            id=f"ev_{len(self._entries) + 1:04d}",
            kind=kind,
            source=source,
            summary=summary,
            locator=dict(locator or {}),
            value=value,
            digest=digest,
        )
        self._entries.append(item)
        self._added.append(item)
        return item

    def get(self, evidence_id: str) -> Evidence | None:
        return next((e for e in self._entries if e.id == evidence_id), None)

    @property
    def entries(self) -> list[Evidence]:
        return list(self._entries)

    def delta(self) -> list[dict[str, Any]]:
        """Only the entries added during this node — the reducer appends them."""
        return [e.to_dict() for e in self._added]


def resolve(evidence: list[dict[str, Any]], ids: list[str]) -> list[dict[str, Any]]:
    index = {item["id"]: item for item in evidence}
    return [index[i] for i in ids if i in index]


def verify_citations(evidence: list[dict[str, Any]], ids: list[str]) -> list[str]:
    """Return the ids that do not exist — a fabricated citation is a hard error.

    Used by the evaluator to measure evidence correctness, and by the report
    builder to refuse to emit a claim pointing at nothing.
    """
    known = {item["id"] for item in evidence}
    return [i for i in ids if i not in known]
