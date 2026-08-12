"""Task-scoped artifact storage for lecture decks and on-demand explainers."""

from __future__ import annotations

import asyncio
from html import escape
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from ..config import REPO_ROOT, Settings

MAX_HTML_BYTES = 512 * 1024
HEX_PATTERN = re.compile(r"#[0-9a-fA-F]{6}\b")
TOKEN_PATTERN = re.compile(r"--c[1-7]\s*:\s*(#[0-9a-fA-F]{6})\b")
DEFAULT_PALETTE = (
    "#7f77dd,#1d9e75,#d85a30,#378add,#ba7517,#d4537e,#639922"
)


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

    def deck_root(self, task_id: str) -> Path:
        return self.task_root(task_id) / "lecture-deck"

    def deck_path(self, task_id: str) -> Path:
        return self.deck_root(task_id) / "dist" / "lecture.html"

    def write_lesson_intro_html(self, task_id: str, result: dict[str, Any]) -> dict[str, Any]:
        """Render lesson-intro JSON into a durable, task-scoped HTML artifact.

        lesson-intro itself intentionally returns structured JSON. This renderer
        is the presentation adapter, so the agent does not get to emit arbitrary
        workspace HTML while the complete lesson-intro result remains persisted.
        """
        selected = result.get("selected_hook") or {}
        research = result.get("research") or {}
        esc = lambda value: escape(str(value or ""))

        def section(title: str, value: Any) -> str:
            text = str(value or "").strip()
            if not text:
                return ""
            return f'<section><h2>{esc(title)}</h2><p>{esc(text).replace(chr(10), "<br>")}</p></section>'

        claims = "".join(
            f'<li><strong>{esc(item.get("status"))}</strong> {esc(item.get("claim"))}'
            f'{("（" + esc(item.get("qualification")) + "）") if item.get("qualification") else ""}</li>'
            for item in research.get("claims", [])
        )
        sources = "".join(
            f'<li><a href="{esc(item.get("url"))}" rel="noreferrer">{esc(item.get("title") or item.get("url"))}</a>'
            f' · Tier {esc(item.get("tier"))}</li>'
            for item in research.get("sources", [])
        )
        evidence = ""
        if claims:
            evidence += f'<section><h2>研究证据账本</h2><ul>{claims}</ul></section>'
        if sources:
            evidence += f'<section><h2>来源</h2><ul>{sources}</ul></section>'
        warnings = "".join(f"<li>{esc(item)}</li>" for item in result.get("warnings", []))
        warning_section = f'<section class="warning"><h2>不确定性</h2><ul>{warnings}</ul></section>' if warnings else ""
        html = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(selected.get("title") or "课程引入")}</title><style>
:root{{--paper:#fbfaf7;--ink:#23231f;--muted:#686762;--rule:rgba(35,35,31,.16);--accent:#534ab7;--accent-fill:#eeedfe;--font-serif:"Songti SC","Source Han Serif SC","SimSun",Georgia,serif;--font-sans:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei","Segoe UI",sans-serif}}*{{box-sizing:border-box}}html,body{{margin:0;min-height:100%;background:#141412;color:var(--ink);font-family:var(--font-sans)}}main{{max-width:960px;margin:0 auto;min-height:100vh;padding:56px clamp(24px,6vw,80px);background:var(--paper)}}.kicker{{margin:0 0 12px;color:var(--accent);font:500 13px var(--font-sans);letter-spacing:.08em}}h1{{margin:0;max-width:780px;font:500 clamp(32px,5vw,52px)/1.18 var(--font-serif)}}.meta{{margin:18px 0 42px;color:var(--muted);font-size:14px}}section{{border-top:.5px solid var(--rule);padding:24px 0}}h2{{margin:0 0 9px;font:500 20px/1.3 var(--font-serif)}}p,li{{color:var(--muted);font-size:16px;line-height:1.8}}p{{margin:0}}ul{{margin:0;padding-left:22px}}a{{color:var(--accent);text-decoration:none}}.warning{{background:var(--accent-fill);padding:20px 22px;border:0}}@media(prefers-color-scheme:dark){{--paper:#1e1e1b;--ink:#f2f0e8;--muted:#b8b6ad;--rule:rgba(242,240,232,.2);--accent:#aaa2ff;--accent-fill:#302e47}}
</style></head><body><main><p class="kicker">LESSON INTRO · {esc(result.get("status", "ok"))}</p><h1>{esc(selected.get("title") or "课程引入")}</h1><p class="meta">知识点：{esc(result.get("topic"))} · 预计 {esc(selected.get("estimated_duration_sec"))} 秒</p>{section("开场", selected.get("opening"))}{section("背景故事", selected.get("story"))}{section("抛给学习者的问题", selected.get("question"))}{section("过渡到知识点", selected.get("transition"))}{section("为什么这个 Hook 有效", selected.get("why_this_hook_works"))}{section("可视化提示", selected.get("visual_cue"))}{evidence}{warning_section}</main></body></html>'''
        encoded = html.encode("utf-8")
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
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            normalized[name] = content
        if not (root / "runtime/index.html").exists() and (self.deck_skill_root / "assets/runtime/index.html").exists():
            target = root / "runtime/index.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text((self.deck_skill_root / "assets/runtime/index.html").read_text(encoding="utf-8"), encoding="utf-8")
            normalized["runtime/index.html"] = target.read_text(encoding="utf-8")
        missing = required - set(normalized)
        if missing:
            raise ArtifactError(f"lecture deck is missing required files: {sorted(missing)}")
        return {"root": str(root), "files": sorted(normalized), "standalone": str(self.deck_path(task_id))}

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
            [str(root), "--strict", "--json"],
            self.deck_skill_root,
        )
        return {"build": build, "validation": validation, "ok": bool(build["ok"] and validation["ok"])}

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
