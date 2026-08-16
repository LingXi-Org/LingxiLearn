"""Public projection for tool events (issue #18 §9.3).

Raw tool input/output stays private.  This module is the single place that
turns a raw tool call/result into the sanitized ``safeParams``/``safeResult``
the Mothership ``ToolCallItem`` may render.  Unknown tools fall back to the
tool name plus a generic status — params and results are omitted, never
``JSON.stringify``-ed wholesale.
"""

from __future__ import annotations

from typing import Any

# Learner-facing display titles; the single authority for tool naming.
# (issue #18 §9.2 — tool display metadata moves off the frontend constants.)
TOOL_DISPLAY: dict[str, str] = {
    "read_skill": "读取技能说明",
    "read_skill_resource": "阅读技能资源",
    "stage_artifact_file": "写入学习产物",
    "stage_artifact_chunk": "续写学习产物",
    "stage_artifact_files": "批量写入学习产物",
    "read_staged_artifact": "检查已生成内容",
    "list_staged_artifacts": "检查产物文件",
    "web_search": "检索资料",
    "web_fetch": "阅读资料",
}

_MAX_VALUE_CHARS = 200


def display_title(tool_name: str) -> str:
    return TOOL_DISPLAY.get(tool_name, "")


def _clip(value: Any, limit: int = _MAX_VALUE_CHARS) -> Any:
    if isinstance(value, str) and len(value) > limit:
        return f"{value[:limit]}…"
    return value


def _bytes_of(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        return len(value.encode("utf-8", errors="replace"))
    if isinstance(value, (bytes, bytearray)):
        return len(value)
    if isinstance(value, (list, tuple)):
        return sum(_bytes_of(item) for item in value)
    if isinstance(value, dict):
        return sum(_bytes_of(item) for item in value.values())
    return 0


def _file_count(files: Any) -> int:
    if isinstance(files, (list, tuple)):
        return len(files)
    return 0


def public_tool_params(tool_name: str, arguments: Any) -> dict[str, Any]:
    """Sanitized call parameters per tool; unknown tools get an empty dict."""

    args = arguments if isinstance(arguments, dict) else {}
    if tool_name == "read_skill":
        return {"skillId": _clip(str(args.get("name") or args.get("skill_id") or ""))}
    if tool_name == "read_skill_resource":
        return {"path": _clip(str(args.get("path") or ""))}
    if tool_name in {"stage_artifact_file", "stage_artifact_chunk"}:
        return {
            "path": _clip(str(args.get("path") or "")),
            "bytes": _bytes_of(args.get("content")),
            **({"mode": str(args.get("mode"))} if args.get("mode") else {}),
        }
    if tool_name == "stage_artifact_files":
        return {
            "fileCount": _file_count(args.get("files")),
            "bytes": _bytes_of(args.get("files")),
        }
    if tool_name in {"read_staged_artifact", "list_staged_artifacts"}:
        return {"path": _clip(str(args.get("path") or ""))}
    if tool_name == "web_search":
        return {"query": _clip(str(args.get("query") or ""))}
    if tool_name == "web_fetch":
        return {"url": _clip(str(args.get("url") or ""))}
    return {}


def public_tool_result(tool_name: str, content: Any, status: Any = None) -> dict[str, Any]:
    """Sanitized result per tool; unknown tools get status only."""

    ok = status in (None, "success", "ok", True)
    if tool_name == "read_skill":
        return {"bytes": _bytes_of(content), "ok": ok}
    if tool_name == "read_skill_resource":
        return {"bytes": _bytes_of(content), "ok": ok}
    if tool_name in {"stage_artifact_file", "stage_artifact_chunk", "stage_artifact_files"}:
        return {"ok": ok, "bytes": _bytes_of(content)}
    if tool_name in {"read_staged_artifact", "list_staged_artifacts"}:
        return {"bytes": _bytes_of(content), "ok": ok}
    if tool_name == "web_search":
        # Content is a ranked result blob; only its size is public.
        return {"bytes": _bytes_of(content), "ok": ok}
    if tool_name == "web_fetch":
        return {"bytes": _bytes_of(content), "ok": ok}
    return {"ok": ok}


def is_known_tool(tool_name: str) -> bool:
    return tool_name in TOOL_DISPLAY


__all__ = [
    "TOOL_DISPLAY",
    "display_title",
    "is_known_tool",
    "public_tool_params",
    "public_tool_result",
]
