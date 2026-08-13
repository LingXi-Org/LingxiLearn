#!/usr/bin/env python3
"""Create a small interactive-lecture-deck authoring project.

The scaffold is intentionally deterministic: it copies the bundled runtime and
page templates, creates one valid opening/content/closing skeleton, and writes
the smallest lecture/manifest records needed for the authoring pass. Existing
files are never overwritten, so rerunning the command is safe.

Usage:
    python init_project.py OUTPUT_DIR --title "课程标题" --slide-count 3
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys


MIN_SLIDES = 3
MAX_SLIDES = 40
TASK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def write_if_missing(path: Path, content: str | bytes, *, binary: bool = False) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    if binary:
        path.write_bytes(content)  # type: ignore[arg-type]
    else:
        path.write_text(content, encoding="utf-8")  # type: ignore[arg-type]
    return True


def replace_once(text: str, replacements: list[tuple[str, str]], path: Path) -> str:
    for old, new in replacements:
        if old not in text:
            raise RuntimeError(f"template marker not found in {path}: {old!r}")
        text = text.replace(old, new, 1)
    return text


def content_slide(template: str, slide_number: int) -> str:
    sid = f"s{slide_number:02d}"
    anchor = f"a-main-relationship-{slide_number:02d}"
    return replace_once(
        template,
        [
            ('id="s02"', f'id="{sid}"'),
            ('data-slide-id="s02"', f'data-slide-id="{sid}"'),
            ('data-anchor="a-main-relationship"', f'data-anchor="{anchor}"'),
            ("把页面标题写成一个可判断的结论", f"第 {slide_number} 页：把核心关系放进图里"),
            ("一句引导足够。解释不要堆在页面上，把注意力交给图。", "先看主关系，再追踪一个关键转折。"),
        ],
        Path("slide-base.html"),
    )


def make_lecture(task_id: str, title: str, slide_count: int, audience: str) -> dict:
    slides: list[dict] = []
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    slides.append(
        {
            "id": "s01",
            "index": 1,
            "role": "opening",
            "file": "slides/s01.html",
            "title": f"{title}：先抓住核心关系",
            "anchors": [],
            "steps": [
                {
                    "id": "s01-01",
                    "order": 1,
                    "kind": "overview",
                    "camera": {"mode": "fit"},
                    "advance": "manual",
                }
            ],
        }
    )

    for number in range(2, slide_count):
        sid = f"s{number:02d}"
        anchor = f"a-main-relationship-{number:02d}"
        title_text = f"第 {number} 页：把核心关系放进图里"
        slides.append(
            {
                "id": sid,
                "index": number,
                "role": "content",
                "file": f"slides/{sid}.html",
                "title": title_text,
                "anchors": [
                    {
                        "id": anchor,
                        "label": "核心关系",
                        "rect": {"x": 64, "y": 208, "w": 1152, "h": 376},
                    }
                ],
                "steps": [
                    {
                        "id": f"{sid}-01",
                        "order": 1,
                        "kind": "overview",
                        "camera": {"mode": "fit"},
                        "advance": "manual",
                    },
                    {
                        "id": f"{sid}-02",
                        "order": 2,
                        "kind": "zoom",
                        "camera": {"mode": "anchor", "anchorId": anchor},
                        "panel": {
                            "placement": "right",
                            "title": "先看这条关系",
                            "body": "先看图中的主关系。它把输入、机制和结果连成一条可追踪的路径。后面每个局部观察，都帮助判断其中一个转折。",
                        },
                        "advance": "manual",
                    },
                    {
                        "id": f"{sid}-03",
                        "order": 3,
                        "kind": "zoom",
                        "camera": {"mode": "anchor", "anchorId": anchor},
                        "panel": {
                            "placement": "right",
                            "title": "把观察迁移出去",
                            "body": "真正要带走的不是某个标签。先找出相似问题的输入、机制和结果，再检查关键条件是否发生变化，并说明边界。",
                        },
                        "advance": "manual",
                    },
                ],
            }
        )

    last = f"s{slide_count:02d}"
    slides.append(
        {
            "id": last,
            "index": slide_count,
            "role": "closing",
            "file": f"slides/{last}.html",
            "title": "最后带走三条可迁移的判断",
            "anchors": [],
            "steps": [
                {
                    "id": f"{last}-01",
                    "order": 1,
                    "kind": "overview",
                    "camera": {"mode": "fit"},
                    "advance": "manual",
                }
            ],
        }
    )

    return {
        "schemaVersion": "zoom-lecture/v2",
        "deck": {
            "id": task_id,
            "title": title,
            "language": "zh-CN",
            "style": "anthropic-academic",
            "canvas": {"width": 1280, "height": 720, "format": "ppt169"},
            "slideDir": "slides",
            "createdAt": now,
            "objectives": [f"面向{audience}理解并迁移核心关系"],
        },
        "defaults": {
            "camera": {"padding": 24},
            "transition": {"inMs": 920, "outMs": 640, "easing": "zoomOut"},
            "highlight": {"style": "outline"},
            "panel": {"placement": "auto", "width": 420},
        },
        "slides": slides,
    }


def make_manifest(task_id: str, title: str, slide_count: int) -> dict:
    return {
        "schemaVersion": "zoom-lecture-manifest/v2",
        "taskId": task_id,
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "deck": {
            "title": title,
            "canvas": {"width": 1280, "height": 720},
            "style": "anthropic-academic",
            "slideCount": slide_count,
            "contentSlideCount": slide_count - 2,
            "stepCount": 2 + (slide_count - 2) * 3,
        },
        "artifacts": {
            "lecture": "lecture.json",
            "slides": [f"slides/s{n:02d}.html" for n in range(1, slide_count + 1)],
            "runtime": "runtime/index.html",
        },
        "validation": {
            "tool": "scripts/validate_deck.py --strict",
            "status": "fail",
            "errors": ["脚手架已创建；完成内容后请运行构建与严格校验"],
            "warnings": [],
        },
        "assumptions": ["脚手架使用 anthropic-academic 默认风格和 fast 质量路径"],
        "deviations": [],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="创建 interactive-lecture-deck 作者工程骨架")
    parser.add_argument("output_dir", help="目标工程目录")
    parser.add_argument("--title", default="交互式讲解课件", help="课件标题")
    parser.add_argument("--task-id", default="lecture-deck", help="小写 kebab-case 任务 ID")
    parser.add_argument("--slide-count", type=int, default=3, help="总页数，含 opening 与 closing")
    parser.add_argument("--audience", default="学习者", help="受众描述")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = Path(args.output_dir).resolve()
    if not TASK_ID_RE.fullmatch(args.task_id):
        print("ERROR --task-id 必须匹配 ^[a-z0-9][a-z0-9-]{0,63}$", file=sys.stderr)
        return 2
    if not MIN_SLIDES <= args.slide_count <= MAX_SLIDES:
        print(f"ERROR --slide-count 必须在 {MIN_SLIDES}..{MAX_SLIDES} 之间", file=sys.stderr)
        return 2
    if not args.title.strip():
        print("ERROR --title 不能为空", file=sys.stderr)
        return 2

    skill_dir = Path(__file__).resolve().parent.parent
    template_dir = skill_dir / "assets" / "templates"
    runtime_template = skill_dir / "assets" / "runtime" / "index.html"
    output.mkdir(parents=True, exist_ok=True)
    for name in ("slides", "runtime", "dist"):
        (output / name).mkdir(exist_ok=True)

    opening = (template_dir / "opening.html").read_text(encoding="utf-8")
    opening = replace_once(
        opening,
        [
            ("课程标题：写清真正要解决的问题", args.title),
            ("一句课程承诺：学完后，学生能够看出 / 判断 / 解释什么。", "先用图把核心关系讲清，再用镜头逐步放大。"),
            ("课程 / 章节 · 受众", f"{args.title} · {args.audience}"),
        ],
        template_dir / "opening.html",
    )
    closing = (template_dir / "closing.html").read_text(encoding="utf-8")
    closing = replace_once(
        closing,
        [
            ("sNN", f"s{args.slide_count:02d}"),
            ('data-slide-id="sNN"', f'data-slide-id="s{args.slide_count:02d}"'),
            ("最后带走的不是步骤，而是三个判断", "最后带走的，是三条可迁移的判断"),
        ],
        template_dir / "closing.html",
    )

    created = 0
    created += int(write_if_missing(output / "slides" / "s01.html", opening))
    base = (template_dir / "slide-base.html").read_text(encoding="utf-8")
    for number in range(2, args.slide_count):
        created += int(write_if_missing(output / "slides" / f"s{number:02d}.html", content_slide(base, number)))
    created += int(write_if_missing(output / "slides" / f"s{args.slide_count:02d}.html", closing))
    created += int(write_if_missing(output / "runtime" / "index.html", runtime_template.read_bytes(), binary=True))

    lecture_path = output / "lecture.json"
    created += int(
        write_if_missing(
            lecture_path,
            json.dumps(make_lecture(args.task_id, args.title, args.slide_count, args.audience), ensure_ascii=False, indent=2) + "\n",
        )
    )
    created += int(
        write_if_missing(
            output / "manifest.json",
            json.dumps(make_manifest(args.task_id, args.title, args.slide_count), ensure_ascii=False, indent=2) + "\n",
        )
    )

    print(f"PASS scaffold={output} slides={args.slide_count} created={created}")
    print("NEXT python scripts/build_standalone.py <project_dir>")
    print("NEXT python scripts/validate_deck.py <project_dir> --strict")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
