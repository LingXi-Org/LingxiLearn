"""Adapter exposing generated task artifacts to application use cases."""

from __future__ import annotations

from ..domain.artifact import GeneratedArtifact
from .artifact_store import ArtifactError, ArtifactStore


class GeneratedArtifactSource:
    def __init__(self, store: ArtifactStore) -> None:
        self._store = store

    def read(self, task_id: str, kind: str) -> GeneratedArtifact | None:
        definitions = {
            "lesson-intro": (
                self._store.lesson_intro_path,
                "lesson-intro.html",
                "text/html; charset=utf-8",
            ),
            "lecture-deck": (
                self._store.deck_path,
                "lecture.html",
                "text/html; charset=utf-8",
            ),
            "visual": (
                self._store.html_path,
                "visual-explainer.html",
                "text/html; charset=utf-8",
            ),
        }
        definition = definitions.get(kind)
        if definition is None:
            return None
        path_factory, filename, mime_type = definition
        try:
            path = path_factory(task_id)
            if not path.is_file():
                return None
            content = path.read_bytes()
        except (OSError, ArtifactError):
            return None
        return GeneratedArtifact(
            kind=kind,
            filename=filename,
            mime_type=mime_type,
            content=content,
        )
