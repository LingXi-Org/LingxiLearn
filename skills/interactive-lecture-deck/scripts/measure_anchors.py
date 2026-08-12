#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用真实浏览器量测锚点矩形，并回写 data-rect 与 lecture.json。

适用场景：锚点高度由内容撑开（内联样式里没写死 height），手算坐标不可靠。

用法:
    python3 measure_anchors.py <project_dir> [--dry-run] [--round 8]

    --dry-run   只打印差异，不写文件
    --round N   把量测结果对齐到 N px 网格（默认 1，即不对齐；设计系统建议 8）

依赖 Playwright（可选）：
    pip install playwright && playwright install chromium
若环境未安装，脚本会明确报错并退出（码 3），不影响 validate_deck.py 的使用。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

RECT_ATTR_RE = re.compile(r'(data-rect\s*=\s*")([^"]*)(")')

MEASURE_JS = """
() => {
  const out = {};
  document.querySelectorAll('[data-anchor]').forEach((el) => {
    const slide = el.closest('.slide');
    if (!slide) return;
    const s = slide.getBoundingClientRect();
    const r = el.getBoundingClientRect();
    out[el.getAttribute('data-anchor')] = {
      x: r.left - s.left,
      y: r.top - s.top,
      w: r.width,
      h: r.height,
    };
  });
  return out;
}
"""


def snap(value: float, grid: int) -> int:
    if grid <= 1:
        return int(round(value))
    return int(round(value / grid) * grid)


def rewrite_html(path: str, measured: dict, grid: int) -> tuple[dict, str]:
    with open(path, encoding="utf-8") as fh:
        html = fh.read()

    updates: dict[str, dict] = {}
    # 逐个锚点元素定位其 data-anchor 与随后的 data-rect
    for aid, box in measured.items():
        rect = {
            "x": snap(box["x"], grid),
            "y": snap(box["y"], grid),
            "w": snap(box["w"], grid),
            "h": snap(box["h"], grid),
        }
        updates[aid] = rect
        pattern = re.compile(
            r'(data-anchor\s*=\s*"' + re.escape(aid) + r'"[^>]*?data-rect\s*=\s*")([^"]*)(")'
        )
        replacement = r"\g<1>" + f"{rect['x']} {rect['y']} {rect['w']} {rect['h']}" + r"\g<3>"
        html, n = pattern.subn(replacement, html)
        if n == 0:
            # data-rect 写在 data-anchor 之前的情况
            pattern2 = re.compile(
                r'(data-rect\s*=\s*")([^"]*)("[^>]*?data-anchor\s*=\s*"' + re.escape(aid) + r'")'
            )
            replacement2 = (
                r"\g<1>" + f"{rect['x']} {rect['y']} {rect['w']} {rect['h']}" + r"\g<3>"
            )
            html, n = pattern2.subn(replacement2, html)
        if n == 0:
            print(f"  [跳过] {aid}: 元素上没有 data-rect 属性，无法回写", file=sys.stderr)
    return updates, html


def main() -> int:
    ap = argparse.ArgumentParser(description="用浏览器量测并回填锚点矩形")
    ap.add_argument("project_dir")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--round", type=int, default=1, dest="grid")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        print(
            "[未安装] 需要 Playwright：pip install playwright && playwright install chromium\n"
            "本脚本是可选工具；不装也可以手写 data-rect 并用 validate_deck.py 校验。",
            file=sys.stderr,
        )
        return 3

    project_dir = os.path.abspath(args.project_dir)
    lecture_path = os.path.join(project_dir, "lecture.json")
    with open(lecture_path, encoding="utf-8") as fh:
        lecture = json.load(fh)

    changed = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        for slide in lecture["slides"]:
            path = os.path.join(project_dir, slide["file"])
            if not os.path.isfile(path):
                print(f"[缺失] {slide['file']}", file=sys.stderr)
                continue
            page.goto("file://" + path)
            measured = page.evaluate(MEASURE_JS)
            if not measured:
                continue

            updates, new_html = rewrite_html(path, measured, args.grid)

            for anchor in slide.get("anchors", []):
                new = updates.get(anchor["id"])
                if not new:
                    continue
                if anchor["rect"] != new:
                    print(
                        f"{slide['id']}/{anchor['id']}: "
                        f"{anchor['rect']} → {new}"
                    )
                    changed += 1
                    if not args.dry_run:
                        anchor["rect"] = new

            if not args.dry_run:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(new_html)
        browser.close()

    if not args.dry_run and changed:
        with open(lecture_path, "w", encoding="utf-8") as fh:
            json.dump(lecture, fh, ensure_ascii=False, indent=2)
            fh.write("\n")

    print(f"\n{'（dry-run）' if args.dry_run else ''}共 {changed} 处锚点矩形与量测值不符")
    print("提示：回写后请重跑 validate_deck.py，focus 可能需要一并更新。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
