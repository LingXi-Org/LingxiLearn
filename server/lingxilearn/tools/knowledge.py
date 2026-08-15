"""Lexical knowledge retrieval over the course pack's reference material.

BM25 over a few hundred chunks, in pure Python.  No vector database, no
embedding service, no index to keep warm — at this corpus size a lexical
ranker is not a compromise, it is the correct engineering choice, and it has
the property that matters for teaching: **the citation is exact and stable**,
so a claim can be traced to a numbered RFC section rather than to a paraphrase.

Chinese is tokenised as character bigrams, which needs no segmenter and works
well for the technical vocabulary this corpus uses.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .registry import registry

_CJK = re.compile(r"[一-鿿]")
_WORD = re.compile(r"[a-z0-9]+(?:\.[a-z0-9]+)*")

K1, B = 1.5, 0.75


def tokenize(text: str) -> list[str]:
    lowered = text.casefold()
    tokens = _WORD.findall(lowered)
    cjk = "".join(_CJK.findall(lowered))
    tokens.extend(cjk[i : i + 2] for i in range(max(0, len(cjk) - 1)))
    tokens.extend(cjk)  # unigrams too, so a single rare character still matches
    return tokens


@dataclass(slots=True)
class Chunk:
    id: str
    source: str
    title: str
    section: str
    text: str
    url: str = ""
    tokens: Counter[str] = field(default_factory=Counter)
    length: int = 0

    def to_hit(self, score: float) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "section": self.section,
            "text": self.text,
            "url": self.url,
            "score": round(score, 4),
        }


class KnowledgeBase:
    def __init__(self) -> None:
        self.chunks: list[Chunk] = []
        self._df: Counter[str] = Counter()
        self._avg_len = 1.0

    def load_dir(self, root: Path) -> int:
        """Load ``*.md`` files. A ``## `` heading starts a new citable chunk."""
        if not root.exists():
            return 0
        added = 0
        for path in sorted(root.rglob("*.md")):
            added += len(self._parse_file(path))
        self._reindex()
        return added

    def _parse_file(self, path: Path) -> list[Chunk]:
        """Split one document into citable chunks, one per ``##`` section."""
        source = title = path.stem
        url = ""
        section = ""
        buffer: list[str] = []
        chunks: list[Chunk] = []

        def emit() -> None:
            body = "\n".join(buffer).strip()
            buffer.clear()
            if not body:
                return
            anchor = section or "intro"
            chunks.append(
                Chunk(
                    id=f"{source}#{anchor}",
                    source=source,
                    title=title,
                    section=anchor,
                    text=body,
                    url=url,
                )
            )

        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
            elif line.startswith("> source:"):
                url = line.split(":", 1)[1].strip()
            elif line.startswith("## "):
                emit()
                section = line[3:].strip()
            else:
                buffer.append(line)
        emit()

        self.chunks.extend(chunks)
        return chunks

    def _reindex(self) -> None:
        self._df = Counter()
        total = 0
        for chunk in self.chunks:
            chunk.tokens = Counter(tokenize(f"{chunk.title} {chunk.section} {chunk.text}"))
            chunk.length = sum(chunk.tokens.values()) or 1
            total += chunk.length
            for token in chunk.tokens:
                self._df[token] += 1
        self._avg_len = (total / len(self.chunks)) if self.chunks else 1.0

    def search(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        if not self.chunks:
            return []
        terms = tokenize(query)
        n = len(self.chunks)
        scored: list[tuple[float, Chunk]] = []
        for chunk in self.chunks:
            score = 0.0
            for term in terms:
                freq = chunk.tokens.get(term, 0)
                if not freq:
                    continue
                idf = math.log(1 + (n - self._df[term] + 0.5) / (self._df[term] + 0.5))
                norm = freq * (K1 + 1) / (
                    freq + K1 * (1 - B + B * chunk.length / self._avg_len)
                )
                score += idf * norm
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda pair: (-pair[0], pair[1].id))
        return [chunk.to_hit(score) for score, chunk in scored[:limit]]


kb = KnowledgeBase()


def configure(roots: list[Path]) -> int:
    """Point the process-wide index at one or more knowledge directories."""
    kb.chunks.clear()
    total = 0
    for root in roots:
        total += kb.load_dir(Path(root))
    return total


@registry.tool("kb.search")
def kb_search(query: str, limit: int = 3) -> list[dict]:
    """Search the protocol reference corpus and return citable chunks."""
    return kb.search(query, limit)
