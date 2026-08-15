"""Task-scoped artifact storage for lecture decks and on-demand explainers."""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..config import REPO_ROOT, Settings

MAX_HTML_BYTES = 512 * 1024
HEX_PATTERN = re.compile(r"#[0-9a-fA-F]{6}\b")
TOKEN_PATTERN = re.compile(r"--c[1-7]\s*:\s*(#[0-9a-fA-F]{6})\b")
TEXT_TAG_RE = re.compile(r"(<text\b)([^>]*)(>)", re.IGNORECASE)
VALID_SVG_TEXT_CLASS = {"t", "ts", "th", "tn"}
DEFAULT_PALETTE = "#7f77dd,#1d9e75,#d85a30,#378add,#ba7517,#d4537e,#639922"


class ArtifactError(RuntimeError):
    """An artifact could not be safely written or validated."""


class ArtifactStore:
    def __init__(self, settings: Settings) -> None:
        self.root = settings.agent_task_dir.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_html_bytes = min(settings.agent_max_html_bytes, MAX_HTML_BYTES)
        self.visual_skill_root = (REPO_ROOT / "skills" / "interactive-visual-explainer").resolve()
        self.skill_root = self.visual_skill_root
        self.deck_skill_root = (REPO_ROOT / "skills" / "interactive-lecture-deck").resolve()
        self.lesson_skill_root = (REPO_ROOT / "skills" / "lesson-intro").resolve()

    def task_root(self, task_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,96}", task_id):
            raise ArtifactError("invalid task id")
        target = (self.root / task_id).resolve()
        if not target.is_relative_to(self.root):
            raise ArtifactError("task path escapes artifact root")
        target.mkdir(parents=True, exist_ok=True)
        return target

    def html_path(self, task_id: str) -> Path:
        return self.task_root(task_id) / "visual-explainer.html"

    def lesson_intro_path(self, task_id: str) -> Path:
        return self.task_root(task_id) / "lesson-intro.html"

    def lesson_intro_draft_path(self, task_id: str) -> Path:
        """Return the durable private draft path used for timeout recovery."""

        return self.task_root(task_id) / ".draft" / "lesson-intro" / "lesson-intro.html"

    def write_lesson_intro_file(self, task_id: str, content: str) -> dict[str, Any]:
        """Persist the current lesson-intro-html.v1 primary artifact."""

        if not isinstance(content, str) or not content.strip():
            raise ArtifactError("lesson-intro HTML must be a non-empty string")
        encoded = content.encode("utf-8")
        if len(encoded) > self.max_html_bytes:
            raise ArtifactError(f"lesson-intro HTML exceeds {self.max_html_bytes} bytes")
        path = self.lesson_intro_path(task_id)
        path.write_bytes(encoded)
        return {
            "artifact_id": "lesson-intro",
            "filename": path.name,
            "bytes": len(encoded),
            "relative_path": f"{task_id}/{path.name}",
        }

    def read_lesson_intro_file(self, task_id: str) -> str:
        path = self.lesson_intro_path(task_id)
        if not path.exists() or not path.is_file():
            raise ArtifactError("lesson-intro artifact is not ready")
        return path.read_text(encoding="utf-8")

    def deck_root(self, task_id: str) -> Path:
        return self.task_root(task_id) / "lecture-deck"

    def deck_path(self, task_id: str) -> Path:
        return self.deck_root(task_id) / "dist" / "lecture.html"

    def write_deck(self, task_id: str, files: dict[str, str]) -> dict[str, Any]:
        required = {"lecture.json", "runtime/index.html", "manifest.json"}
        normalized: dict[str, str] = {}
        root = self.deck_root(task_id).resolve()
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)
        for raw_name, content in files.items():
            name = str(raw_name).replace("\\", "/").lstrip("./")
            target = (root / name).resolve()
            if not target.is_relative_to(root) or name.startswith("/"):
                raise ArtifactError("lecture deck path escapes artifact root")
            if not isinstance(content, str) or not content.strip():
                raise ArtifactError(f"empty lecture deck file: {name}")
            if len(content.encode("utf-8")) > self.max_html_bytes:
                raise ArtifactError(
                    f"lecture deck file exceeds {self.max_html_bytes} bytes: {name}"
                )
            if name == "lecture.json":
                content = _normalize_lecture_json(content)
            elif name.startswith("slides/") and name.endswith(".html"):
                content = _normalize_slide_html(content)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            normalized[name] = content
        missing = required - set(normalized)
        if missing:
            raise ArtifactError(f"lecture deck is missing required files: {sorted(missing)}")
        return {
            "root": str(root),
            "files": sorted(normalized),
            "standalone": str(self.deck_path(task_id)),
        }

    async def recover_deck_draft(self, task_id: str) -> dict[str, Any] | None:
        """Promote a staged deck after the generating Agent is interrupted.

        Deck generation is multi-file and can be interrupted after the model has
        written the source files but before it emits its receipt.  Keep that
        source around long enough to run the same narrow normalization and final
        build/validation path used by the normal publish flow.
        """

        draft = self.task_root(task_id) / ".draft" / "deck"
        if not draft.exists() or not draft.is_dir():
            return None
        files: dict[str, str] = {}
        try:
            for path in draft.rglob("*"):
                if path.is_file():
                    rel = path.relative_to(draft).as_posix()
                    files[rel] = path.read_text(encoding="utf-8")
            if not files:
                return None
            staged = self.write_deck(task_id, files)
            validation = await self.build_and_validate_deck(task_id)
        except (OSError, UnicodeError, ArtifactError):
            return None
        if not validation["ok"]:
            return None
        shutil.rmtree(draft, ignore_errors=True)
        return {**staged, "validation": validation, "recovered": True}

    async def build_and_validate_deck(self, task_id: str) -> dict[str, Any]:
        root = self.deck_root(task_id)
        build = await asyncio.to_thread(
            _run_python,
            sys.executable,
            self.deck_skill_root / "scripts" / "build_standalone.py",
            [str(root)],
            self.deck_skill_root,
        )
        validation = await asyncio.to_thread(
            _run_python,
            sys.executable,
            self.deck_skill_root / "scripts" / "validate_deck.py",
            # Warnings describe polish opportunities (layout overlap, wording
            # length, or teaching tone). They must not make an otherwise
            # buildable lecture abort the learner workflow. The validator
            # still returns non-zero for structural/runtime errors.
            [str(root), "--json"],
            self.deck_skill_root,
        )
        return {
            "build": build,
            "validation": validation,
            "ok": bool(build["ok"] and validation["ok"]),
        }

    def write_html(self, task_id: str, content: str) -> dict[str, Any]:
        if not isinstance(content, str) or not content.strip():
            raise ArtifactError("HTML content must be a non-empty string")
        encoded = content.encode("utf-8")
        if len(encoded) > self.max_html_bytes:
            raise ArtifactError(f"HTML exceeds {self.max_html_bytes} bytes")
        path = self.html_path(task_id)
        path.write_bytes(encoded)
        return {
            "artifact_id": "visual",
            "filename": path.name,
            "bytes": len(encoded),
            "relative_path": f"{task_id}/{path.name}",
        }

    def read_html(self, task_id: str) -> bytes:
        path = self.html_path(task_id)
        if not path.exists() or not path.is_file():
            raise ArtifactError("visual artifact is not ready")
        return path.read_bytes()

    async def validate_html(self, task_id: str) -> dict[str, Any]:
        path = self.html_path(task_id)
        if not path.exists():
            raise ArtifactError("visual artifact is not ready")
        node = shutil.which("node")
        if node is None:
            return {
                "ok": False,
                "static": {"ok": False, "error": "node_not_found"},
                "palette": {"light": "skipped", "dark": "skipped"},
                "screenshot": "skipped",
            }

        check_script = self.skill_root / "scripts" / "check_page.js"
        palette_script = self.skill_root / "scripts" / "validate_palette.js"
        static = await asyncio.to_thread(
            _run_node, node, check_script, [str(path)], self.visual_skill_root
        )

        source = path.read_text(encoding="utf-8")
        colors = TOKEN_PATTERN.findall(source)
        if len(colors) < 2:
            colors = HEX_PATTERN.findall(source)
        palette = ",".join(dict.fromkeys(colors)) if len(colors) >= 2 else DEFAULT_PALETTE
        palette_results: dict[str, Any] = {}
        for mode in ("light", "dark"):
            palette_results[mode] = await asyncio.to_thread(
                _run_node,
                node,
                palette_script,
                [palette, "--mode", mode],
                self.visual_skill_root,
            )

        return {
            "ok": bool(static["ok"] and all(item["ok"] for item in palette_results.values())),
            "static": static,
            "palette": palette_results,
            "screenshot": "deferred_to_frontend",
        }

    async def validate_lesson_intro(self, task_id: str) -> dict[str, Any]:
        """Run the current lesson-intro HTML contract validator."""

        path = self.lesson_intro_path(task_id)
        if not path.exists():
            raise ArtifactError("lesson-intro artifact is not ready")
        validation = await asyncio.to_thread(
            _run_python,
            sys.executable,
            REPO_ROOT / "skills" / "lesson-intro" / "scripts" / "validate_output.py",
            [str(path)],
            REPO_ROOT / "skills" / "lesson-intro",
        )
        return {
            "ok": validation["ok"],
            "contract": "lesson-intro-html.v1",
            "validation": validation,
        }

    async def recover_lesson_intro_draft(self, task_id: str) -> dict[str, Any] | None:
        """Promote a valid lesson draft after the generating Agent was interrupted."""

        draft = self.lesson_intro_draft_path(task_id)
        if not draft.exists() or not draft.is_file():
            return None
        try:
            content = draft.read_text(encoding="utf-8")
            artifact = self.write_lesson_intro_file(task_id, content)
            validation = await self.validate_lesson_intro(task_id)
        except (OSError, UnicodeError, ArtifactError):
            return None
        if not validation["ok"]:
            return None
        draft.unlink(missing_ok=True)
        return {**artifact, "validation": validation, "recovered": True}

    async def validate_quiz_result(self, task_id: str, result: dict[str, Any]) -> dict[str, Any]:
        """Run the quiz skill's contract validator against an internal result."""

        path = self.task_root(task_id) / ".quiz-result-validation.json"
        path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        try:
            return await asyncio.to_thread(
                _run_python,
                sys.executable,
                REPO_ROOT / "skills" / "quiz-generator" / "scripts" / "quiz_contract.py",
                ["validate-result", str(path)],
                REPO_ROOT / "skills" / "quiz-generator",
            )
        finally:
            path.unlink(missing_ok=True)


def _run_node(node: str, script: Path, args: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [node, str(script), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    return {
        "ok": completed.returncode == 0,
        "exit_code": completed.returncode,
        "output": ((completed.stdout or "") + (completed.stderr or ""))[-12000:],
    }


def _normalize_lecture_json(content: str) -> str:
    """Migrate common pre-v2 shorthand before strict validation.

    The model may still have cached an older lecture-data contract. Normalize
    only lossless aliases and move legacy metadata to ``extensions``; the
    learner-facing geometry and prose remain unchanged.
    """

    try:
        data = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return content

    changed = False
    if not isinstance(data, dict):
        return content

    deck = data.get("deck")
    if isinstance(deck, dict):
        canvas = deck.get("canvas")
        if isinstance(canvas, dict):
            if "width" not in canvas and "w" in canvas:
                canvas["width"] = canvas.pop("w")
                changed = True
            if "height" not in canvas and "h" in canvas:
                canvas["height"] = canvas.pop("h")
                changed = True
            if "format" not in canvas:
                canvas["format"] = "ppt169"
                changed = True
        if "slideDir" not in deck:
            deck["slideDir"] = "slides"
            changed = True
        if "createdAt" not in deck:
            deck["createdAt"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            changed = True

        # These fields belonged to the pre-v2 deck envelope. Preserve them in
        # an extension instead of letting json-schema reject the whole deck.
        legacy_deck = {
            key: deck.pop(key) for key in ("course", "subtitle", "durationSec") if key in deck
        }
        if legacy_deck:
            extensions = data.setdefault("extensions", {})
            if isinstance(extensions, dict):
                extensions.setdefault("legacyDeck", {}).update(legacy_deck)
            changed = True

    defaults = data.get("defaults")
    if isinstance(defaults, dict):
        # Old defaults used flat aliases. The v2 schema nests panel options.
        panel_placement = defaults.pop("panelPlacement", None)
        if panel_placement is not None:
            panel = defaults.setdefault("panel", {})
            if isinstance(panel, dict) and "placement" not in panel:
                panel["placement"] = panel_placement
            changed = True
        if "advance" in defaults:
            defaults.pop("advance", None)
            changed = True
    for slide in data.get("slides", []) if isinstance(data, dict) else []:
        if not isinstance(slide, dict):
            continue
        for anchor in slide.get("anchors", []) or []:
            if not isinstance(anchor, dict):
                continue
            label = anchor.get("label")
            if not isinstance(label, str) or not label.strip():
                anchor_id = str(anchor.get("id") or "").strip()
                anchor["label"] = anchor_id or "视觉锚点"
                changed = True
            rect = anchor.get("rect")
            if (
                isinstance(rect, list)
                and len(rect) == 4
                and all(
                    isinstance(value, (int, float)) and not isinstance(value, bool)
                    for value in rect
                )
            ):
                anchor["rect"] = dict(zip(("x", "y", "w", "h"), rect))
                changed = True

        for step in slide.get("steps", []) or []:
            if not isinstance(step, dict):
                continue
            if step.get("advance") != "manual":
                step["advance"] = "manual"
                changed = True
            if step.get("kind") == "overview":
                camera = step.get("camera")
                if not isinstance(camera, dict):
                    camera = {}
                    step["camera"] = camera
                    changed = True
                if camera.get("mode") != "fit":
                    camera["mode"] = "fit"
                    changed = True
                for key in ("anchorId", "depth", "scale", "focus"):
                    if key in camera:
                        camera.pop(key, None)
                        changed = True

    if not changed:
        return content
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _normalize_slide_html(content: str) -> str:
    """Add the neutral ``t`` class to SVG text omitted by older generators.

    The slide validator remains strict.  This repair only fills the visual
    contract's presentation class; it does not alter slide geometry or prose.
    """

    changed = False

    def replace_text_tag(match: re.Match[str]) -> str:
        nonlocal changed
        prefix, attrs, suffix = match.groups()
        class_match = re.search(r"\bclass\s*=\s*(['\"])(.*?)\1", attrs, re.IGNORECASE | re.DOTALL)
        if class_match:
            classes = class_match.group(2).split()
            if VALID_SVG_TEXT_CLASS.intersection(classes):
                return match.group(0)
            quote = class_match.group(1)
            replacement = f"class={quote}{class_match.group(2)} t{quote}"
            changed = True
            attrs = attrs[: class_match.start()] + replacement + attrs[class_match.end() :]
            return prefix + attrs + suffix
        changed = True
        return prefix + ' class="t"' + attrs + suffix

    normalized = TEXT_TAG_RE.sub(replace_text_tag, content)
    return normalized if changed else content


def _run_python(python: str, script: Path, args: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [python, str(script), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    return {
        "ok": completed.returncode == 0,
        "exit_code": completed.returncode,
        "output": ((completed.stdout or "") + (completed.stderr or ""))[-20000:],
    }
