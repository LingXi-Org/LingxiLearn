#!/usr/bin/env python3
"""Validate a lesson-intro single-file HTML artifact or its optional JSON envelope."""

from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


FORBIDDEN_VISIBLE_PATTERNS = (
    r"https?://",
    r"作为\s*AI",
    r"本\s*(?:Agent|Skill|智能体)",
    r"(?:任务\s*(?:ID|信息|结果|参数)|运行时|调试(?:信息|日志|语句)?|开发性(?:语句|内容)?|编排|解析|校验|回退|重试|提示词)",
    r"(?:task[_ -]?id|schema|json|yaml|web_search|web_fetch|runtime|debug|fallback|token)",
    r"(?:搜索角度|搜索次数|抓取次数|候选(?:方案|项)?|评分|排名|置信度|证据[_ -]?ID|source[_ -]?id|claim-to-source)",
    r"(?:verified|qualified|rejected|insufficient_evidence)",
    r"(?:根据用户需求|根据任务|以下是(?:生成|研究)结果|本次(?:生成|研究)|系统将|调用工具)",
)

INTERNAL_SCRIPT_PATTERN = re.compile(
    r"(?:task[_ -]?id|schema_version|structured_data|search_calls|fetch_calls|query_results|"
    r"aggregated_results|source_records|source_ids|claim-to-source|research|claims|sources|"
    r"web_search|web_fetch|runtime|debug|candidate[_ -]?score)",
    re.IGNORECASE,
)
NETWORK_SCRIPT_PATTERN = re.compile(
    r"(?:fetch\s*\(|XMLHttpRequest|WebSocket\s*\(|EventSource\s*\(|import\s*\()",
    re.IGNORECASE,
)


def fail(message: str) -> None:
    raise ValueError(message)


class VisibleTextParser(HTMLParser):
    """Collect visible text and basic document structure without third-party dependencies."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.visible_parts: list[str] = []
        self.h1_count = 0
        self.h2_count = 0
        self.html_lang = ""
        self.body_count = 0
        self.title_parts: list[str] = []
        self.in_title = False
        self.skip_depth = 0
        self.external_resource = False
        self.network_api = False
        self.internal_comment = False
        self.data_attribute = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attributes = {key.lower(): value or "" for key, value in attrs}
        if tag == "html":
            self.html_lang = attributes.get("lang", "")
        if tag == "body":
            self.body_count += 1
        if tag == "h1":
            self.h1_count += 1
        elif tag == "h2":
            self.h2_count += 1
        if tag == "title":
            self.in_title = True
        if any(key.startswith("data-") for key in attributes):
            self.data_attribute = True
        if tag == "link" or (tag == "script" and attributes.get("src")):
            self.external_resource = True
        for key, value in attributes.items():
            if key in {"src", "href", "action", "poster"} and re.match(r"(?i)https?://", value):
                self.external_resource = True
        if tag in {"script", "style", "template"}:
            self.skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self.in_title = False
        if tag in {"script", "style", "template"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        if self.skip_depth == 0 and data.strip():
            self.visible_parts.append(data)
        if self.skip_depth and (
            INTERNAL_SCRIPT_PATTERN.search(data) or NETWORK_SCRIPT_PATTERN.search(data)
        ):
            self.network_api = True

    def handle_comment(self, data: str) -> None:
        if INTERNAL_SCRIPT_PATTERN.search(data):
            self.internal_comment = True

    @property
    def visible_text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.visible_parts)).strip()

    @property
    def title(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.title_parts)).strip()


def validate_html(html: str) -> None:
    if not re.search(r"(?is)<!doctype\s+html", html):
        fail("HTML must start with a doctype declaration")
    parser = VisibleTextParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception as exc:  # noqa: BLE001 - convert parser details to a compact validation error
        fail(f"HTML parsing failed: {exc}")
    if parser.html_lang.lower() != "zh-cn":
        fail("HTML must declare <html lang=\"zh-CN\">")
    if parser.body_count != 1:
        fail("HTML must contain exactly one body")
    if not parser.title:
        fail("HTML must contain a meaningful title")
    if parser.h1_count != 1:
        fail("HTML must contain exactly one h1")
    if parser.h2_count > 2:
        fail("HTML may contain at most two h2 headings")
    if len(re.findall(r"(?is)<figure\b", html)) < 1 or len(re.findall(r"(?is)<figcaption\b", html)) < 1:
        fail("HTML must contain a dominant figure with a figcaption")
    svg_tags = re.findall(r"(?is)<svg\b([^>]*)>", html)
    if not svg_tags:
        fail("HTML must contain an inline SVG concept visual")
    if not all(re.search(r"(?i)\bviewbox\s*=\s*['\"]0\s+0\s+680\s+\d+", attrs) for attrs in svg_tags):
        fail("SVG viewBox must use width 680")
    for attrs in re.findall(r"(?is)<text\b([^>]*)>", html):
        class_match = re.search(r"(?i)\bclass\s*=\s*['\"]([^'\"]+)['\"]", attrs)
        if not class_match or not re.search(r"(?:^|\s)(?:t|ts|th|tn)(?:\s|$)", class_match.group(1)):
            fail("every SVG text element must use class t, ts, th, or tn")
    required_tokens = ("--paper", "--surface", "--ink-1", "--ink-2", "--rule", "--accent", "--font-serif", "--font-sans", "--font-mono")
    if not all(token in html for token in required_tokens):
        fail("HTML must use the shared visual tokens")
    if not re.search(r"(?is)prefers-color-scheme\s*:\s*dark", html):
        fail("HTML must define an explicit dark mode")
    if not re.search(r"(?is)@media\s+print", html):
        fail("HTML must define a print fallback")
    if re.search(r"(?is)(?:linear|radial)-gradient|box-shadow|drop-shadow|backdrop-filter|\bfilter\s*:", html):
        fail("HTML must not use gradients, shadows, blur, or filters")
    if re.search(r"(?is)font-weight\s*:\s*(?:600|700|800|900)\b", html):
        fail("HTML may use only 400/500 font weights")
    if re.search(r"(?is)border-radius\s*:\s*(?:1[3-9]|[2-9]\d|\d{3,})px", html):
        fail("HTML must use radii no larger than 12px")
    if len(parser.visible_text) < 60:
        fail("HTML visible text is too short to form a useful lesson introduction")
    if parser.external_resource:
        fail("HTML must be self-contained and must not load external resources")
    if parser.network_api:
        fail("HTML must not contain network calls or internal metadata in scripts")
    if parser.internal_comment:
        fail("HTML comments must not contain internal metadata")
    if parser.data_attribute:
        fail("HTML must not hide internal parameters in data-* attributes")
    for pattern in FORBIDDEN_VISIBLE_PATTERNS:
        if re.search(pattern, parser.visible_text, re.IGNORECASE):
            fail(f"HTML visible text contains internal or development-facing text: {pattern}")


def require(obj: dict, key: str, expected=None):
    if key not in obj:
        fail(f"missing required key: {key}")
    value = obj[key]
    if expected is not None and not isinstance(value, expected):
        label = expected.__name__ if hasattr(expected, "__name__") else str(expected)
        fail(f"{key} must be {label}")
    return value


def validate_envelope(data: dict) -> None:
    html = require(data, "html", str)
    forbidden_machine_keys = {
        "research", "claims", "sources", "source_records", "query_results", "aggregated_results",
        "search_calls", "fetch_calls", "visible_citations",
    }
    forbidden = forbidden_machine_keys & data.keys()
    if forbidden:
        fail(f"lesson-intro no longer accepts search or source aggregation fields: {sorted(forbidden)}")
    structured = data.get("structured_data")
    if structured is not None:
        structured = require(data, "structured_data", dict)
        input_data = structured.get("input")
        if input_data is not None and isinstance(input_data, dict):
            if input_data.get("language", "zh-CN") != "zh-CN":
                fail("lesson-intro-html.v1 requires zh-CN output")
        forbidden = forbidden_machine_keys & structured.keys()
        if forbidden:
            fail(f"structured_data contains removed search or source fields: {sorted(forbidden)}")
    status = data.get("status")
    if status is not None and status != "ok":
        fail("invalid status")
    validate_html(html)


def validate_input(text: str) -> None:
    stripped = text.lstrip("\ufeff \t\r\n")
    if re.match(r"(?is)<!doctype\s+html", stripped):
        validate_html(stripped)
        return
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        fail(f"input must be HTML or a JSON envelope: {exc}")
    if not isinstance(data, dict):
        fail("JSON envelope must be an object")
    validate_envelope(data)


def main() -> int:
    if len(sys.argv) != 2:
        print("用法：validate_output.py RESULT.html|RESULT.json", file=sys.stderr)
        return 2
    try:
        validate_input(Path(sys.argv[1]).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - CLI must report a compact validation error
        print(f"校验失败：{exc}", file=sys.stderr)
        return 1
    print("校验通过：lesson-intro-html.v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
