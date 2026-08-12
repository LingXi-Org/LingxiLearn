#!/usr/bin/env python3
"""Compile a Zoom Lecture Deck project into one dependency-free HTML file.

The resulting file embeds lecture.json and every slide HTML document, and runs by
opening it directly from file://. Python is only a build-time tool; it is not
needed to view the compiled lecture.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

BUNDLE_RE = re.compile(
    r'(<!-- ZOOM_BUNDLE_START --><script id="zoomLectureBundle" type="application/json">)(.*?)(</script><!-- ZOOM_BUNDLE_END -->)',
    re.S,
)


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def safe_json_for_html(obj) -> str:
    # Prevent embedded HTML strings from ever closing the JSON script element.
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return (
        text.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def normalize_rel(path: str) -> str:
    return path.replace("\\", "/").removeprefix("./")


def compile_deck(project_dir: Path, runtime_path: Path, output_path: Path) -> None:
    lecture_path = project_dir / "lecture.json"
    if not lecture_path.is_file():
        raise FileNotFoundError(f"missing {lecture_path}")
    if not runtime_path.is_file():
        raise FileNotFoundError(f"missing runtime template {runtime_path}")

    lecture = load_json(lecture_path)
    slides = {}
    for slide in lecture.get("slides", []):
        rel = normalize_rel(str(slide.get("file", "")))
        if not rel:
            raise ValueError(f"slide {slide.get('id', '?')} has no file")
        src = project_dir / rel
        if not src.is_file():
            raise FileNotFoundError(f"missing slide file: {src}")
        html = src.read_text(encoding="utf-8")
        slides[rel] = html
        sid = slide.get("id")
        if sid:
            slides.setdefault(str(sid), html)

    bundle = {
        "format": "zoom-lecture-standalone/v1",
        "lecture": lecture,
        "slides": slides,
    }
    runtime = runtime_path.read_text(encoding="utf-8")
    if not BUNDLE_RE.search(runtime):
        raise RuntimeError("runtime template is missing ZOOM_BUNDLE_START/END markers")

    payload = safe_json_for_html(bundle)
    marker_match = BUNDLE_RE.search(runtime)
    if marker_match is None:
        raise RuntimeError("runtime template is missing bundle payload region")
    start, end = marker_match.span(2)
    compiled = runtime[:start] + payload + runtime[end:]

    title = str(lecture.get("deck", {}).get("title") or "Zoom Lecture")
    compiled = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", compiled, count=1, flags=re.S)
    compiled = compiled.replace(
        '<div class="runtime" id="app">',
        '<div class="runtime" id="app" data-zoom-standalone="true">',
        1,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(compiled, encoding="utf-8")

    size_kib = output_path.stat().st_size / 1024
    print(f"PASS standalone={output_path} slides={len(lecture.get('slides', []))} size={size_kib:.1f}KiB")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile Zoom Lecture Deck into one offline HTML file")
    parser.add_argument("project_dir", help="deck project directory containing lecture.json and slides/")
    parser.add_argument("-o", "--output", help="output HTML path; default: <project>/dist/lecture.html")
    parser.add_argument("--runtime", help="runtime template path; default: <project>/runtime/index.html")
    args = parser.parse_args()

    project = Path(args.project_dir).resolve()
    runtime = Path(args.runtime).resolve() if args.runtime else project / "runtime" / "index.html"
    output = Path(args.output).resolve() if args.output else project / "dist" / "lecture.html"
    try:
        compile_deck(project, runtime, output)
    except Exception as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
