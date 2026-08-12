#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
interactive-lecture-deck 校验器

用法:
    python3 validate_deck.py <project_dir> [--json] [--strict]

    <project_dir>   包含 lecture.json 与 slides/ 的工程目录
    --json          以 JSON 输出结果（供主智能体机读）
    --strict        把 WARNING 也当作失败

退出码: 0 = 通过（可能有 warning）; 1 = 有 ERROR; 2 = 用法/读取错误
仅依赖标准库；若环境装有 jsonschema，会额外做一次 schema 校验。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from html.parser import HTMLParser

CANVAS_W = 1280
CANVAS_H = 720
DEPTH_SCALES = {1: 1.25, 2: 1.5, 3: 1.8, 4: 2.2, 5: 3.5, 6: 5.0}
MIN_SCALE, MAX_SCALE = 1.05, 6.0

MIN_ANCHOR_W, MIN_ANCHOR_H = 180, 72
EDGE_CLEARANCE = 40
ANCHOR_GAP = 24
PANEL_MIN_CHARS, PANEL_MAX_CHARS = 45, 140
SLIDE_TEXT_WARN, SLIDE_TEXT_MAX = 110, 140
ALLOWED_VISUAL_TYPES = {
    "diagram", "chart", "process", "timeline", "comparison", "formula",
    "geometry", "system", "table", "image", "concept-map",
}
AIISH_PANEL_PHRASES = (
    "接下来我们来看", "我们可以看到", "可以看到", "显而易见", "不难发现",
    "综上所述", "首先", "其次", "最后", "需要注意的是",
)
DEFAULT_PADDING = 24

SCHEMA_VERSION = "zoom-lecture/v2"
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(SKILL_DIR, "references", "lecture.schema.json")

ANCHOR_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,39}$")
SLIDE_ID_RE = re.compile(r"^s\d{2}$")
STEP_ID_RE = re.compile(r"^s\d{2}-\d{2}$")
RECT_RE = re.compile(r"^\s*(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s*$")
PX_RE = re.compile(r"(-?[\d.]+)px")


# --------------------------------------------------------------------------- #
# 结果收集
# --------------------------------------------------------------------------- #
class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"{where}: {msg}")

    @property
    def status(self) -> str:
        if self.errors:
            return "fail"
        return "pass-with-warnings" if self.warnings else "pass"


# --------------------------------------------------------------------------- #
# HTML 解析
# --------------------------------------------------------------------------- #
VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


class SlideParser(HTMLParser):
    """抽取幻灯片结构：根节点属性、锚点、样式文本、违禁标签。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.slide_attrs: dict[str, str] | None = None
        self.anchors: dict[str, dict] = {}
        self.duplicate_anchor_ids: list[str] = []
        self.style_text: list[str] = []
        self.has_script = False
        self.external_links: list[str] = []
        self.remote_images: list[str] = []
        self.slide_depth: int | None = None
        self._depth = 0
        self._in_style = False
        self._top_level_blocks = 0
        self.visuals: list[dict] = []
        self.visible_text: list[str] = []
        self.svg_text_missing_class: list[str] = []
        self._svg_level = 0

    # -- helpers ----------------------------------------------------------- #
    @staticmethod
    def _attrs(attrs) -> dict[str, str]:
        return {k.lower(): (v if v is not None else "") for k, v in attrs}

    # -- events ------------------------------------------------------------ #
    def handle_starttag(self, tag, attrs):
        a = self._attrs(attrs)
        self._depth += 1

        if tag == "script":
            self.has_script = True
        elif tag == "style":
            self._in_style = True
        elif tag == "link":
            href = a.get("href", "")
            if href:
                self.external_links.append(href)
        elif tag == "img":
            src = a.get("src", "")
            if src and not src.startswith("data:"):
                self.remote_images.append(src)

        classes = a.get("class", "").split()
        if tag == "svg":
            self._svg_level += 1
        if tag == "text" and self._svg_level > 0:
            if not ({"t", "ts", "th", "tn"} & set(classes)):
                self.svg_text_missing_class.append(a.get("id", "<svg text>"))

        visual_type = a.get("data-visual")
        if visual_type:
            self.visuals.append({"type": visual_type, "tag": tag, "style": a.get("style", "")})

        if self.slide_attrs is None and "slide" in classes:
            self.slide_attrs = a
            self.slide_depth = self._depth
        elif self.slide_depth is not None and self._depth == self.slide_depth + 1:
            self._top_level_blocks += 1

        anchor_id = a.get("data-anchor")
        if anchor_id:
            if anchor_id in self.anchors:
                self.duplicate_anchor_ids.append(anchor_id)
            self.anchors[anchor_id] = {
                "data-rect": a.get("data-rect"),
                "style": a.get("style", ""),
                "tag": tag,
            }

        # 空元素不会触发 endtag，立即回退深度，避免嵌套层级失真
        if tag in VOID_TAGS:
            self._depth -= 1

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "style":
            self._in_style = False
        if tag == "svg" and self._svg_level > 0:
            self._svg_level -= 1
        self._depth = max(0, self._depth - 1)

    def handle_data(self, data):
        if self._in_style:
            self.style_text.append(data)
        elif self.slide_depth is not None and self._depth >= self.slide_depth:
            t = data.strip()
            if t:
                self.visible_text.append(t)

    @property
    def css(self) -> str:
        return "\n".join(self.style_text)

    @property
    def top_level_blocks(self) -> int:
        return self._top_level_blocks

    @property
    def visible_text_len(self) -> int:
        return cjk_len(" ".join(self.visible_text))


def parse_inline_px(style: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for decl in style.split(";"):
        if ":" not in decl:
            continue
        prop, value = decl.split(":", 1)
        prop = prop.strip().lower()
        if prop in ("left", "top", "width", "height"):
            m = PX_RE.search(value)
            if m:
                out[prop] = float(m.group(1))
    return out


# --------------------------------------------------------------------------- #
# 几何
# --------------------------------------------------------------------------- #
def rect_center_focus(rect: dict) -> tuple[float, float]:
    return (rect["x"] + rect["w"] / 2) / CANVAS_W, (rect["y"] + rect["h"] / 2) / CANVAS_H


def resolve_scale(camera: dict, rect: dict, default_depth, default_padding) -> float:
    if "scale" in camera:
        s = float(camera["scale"])
    elif "depth" in camera:
        s = DEPTH_SCALES[int(camera["depth"])]
    elif default_depth is not None:
        s = DEPTH_SCALES[int(default_depth)]
    else:
        pad = camera.get("padding", default_padding)
        s = min(CANVAS_W / (rect["w"] + 2 * pad), CANVAS_H / (rect["h"] + 2 * pad))
    return max(MIN_SCALE, min(MAX_SCALE, s))


def rects_overlap(a: dict, b: dict, gap: int = 0) -> bool:
    return not (
        a["x"] + a["w"] + gap <= b["x"]
        or b["x"] + b["w"] + gap <= a["x"]
        or a["y"] + a["h"] + gap <= b["y"]
        or b["y"] + b["h"] + gap <= a["y"]
    )


def cjk_len(text: str) -> int:
    """按「汉字算 1、连续 ASCII 词算 1」粗略估算篇幅。"""
    stripped = re.sub(r"[`*_>#\-\[\]()]", "", text)
    cjk = len(re.findall(r"[一-鿿　-〿＀-￯]", stripped))
    words = len(re.findall(r"[A-Za-z0-9]+", stripped))
    return cjk + words


# --------------------------------------------------------------------------- #
# 校验
# --------------------------------------------------------------------------- #
def validate_json_schema(data, rep: Report) -> None:
    try:
        import jsonschema  # type: ignore
    except ImportError:
        rep.warn("env", "未安装 jsonschema，已跳过 JSON Schema 校验（结构检查仍然执行）")
        return
    try:
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
    except OSError as exc:
        rep.warn("env", f"读取 schema 失败，跳过：{exc}")
        return
    validator = jsonschema.Draft202012Validator(schema)
    for e in sorted(validator.iter_errors(data), key=lambda x: list(x.path)):
        path = "/".join(str(p) for p in e.path) or "<root>"
        rep.err(f"schema:{path}", e.message)


def validate_slide_html(path: str, slide: dict, rep: Report) -> SlideParser | None:
    where = f"{slide['id']}"
    try:
        with open(path, encoding="utf-8") as fh:
            html = fh.read()
    except OSError as exc:
        rep.err(where, f"幻灯片文件读取失败：{exc}")
        return None

    p = SlideParser()
    p.feed(html)
    p.close()

    if p.slide_attrs is None:
        rep.err(where, "找不到 class 含 'slide' 的根节点")
        return p

    if p.slide_attrs.get("data-slide-id") != slide["id"]:
        rep.err(
            where,
            f"根节点 data-slide-id={p.slide_attrs.get('data-slide-id')!r} "
            f"与 lecture.json 的 id={slide['id']!r} 不一致",
        )
    if p.slide_attrs.get("data-canvas") != f"{CANVAS_W}x{CANVAS_H}":
        rep.err(where, f"根节点 data-canvas 必须为 {CANVAS_W}x{CANVAS_H}")
    if p.slide_attrs.get("data-slide-role") != slide.get("role"):
        rep.err(where, f"根节点 data-slide-role={p.slide_attrs.get('data-slide-role')!r} 与 lecture.json role={slide.get('role')!r} 不一致")
    if p.slide_attrs.get("data-style") != "anthropic-academic":
        rep.err(where, "data-style 必须为 'anthropic-academic'")

    css = p.css
    if not re.search(r"\.slide\s*\{[^}]*width\s*:\s*1280px", css, re.S):
        rep.err(where, ".slide 未写死 width:1280px")
    if not re.search(r"\.slide\s*\{[^}]*height\s*:\s*720px", css, re.S):
        rep.err(where, ".slide 未写死 height:720px")

    if p.has_script:
        rep.err(where, "页面包含 <script>，禁止")
    for href in p.external_links:
        if not href.startswith("data:"):
            rep.err(where, f"存在外部 <link href={href!r}>，页面必须自包含")
    for src in p.remote_images:
        rep.err(where, f"存在非 data: 图片 src={src!r}，页面必须自包含")
    if "@import" in css:
        rep.err(where, "CSS 使用了 @import，页面必须自包含")
    if re.search(r"position\s*:\s*(fixed|sticky)", css):
        rep.err(where, "使用了 position:fixed/sticky，与外层 transform 冲突")
    if re.search(r"@media", css):
        rep.err(where, "存在 @media 查询，页面不允许响应式")
    if re.search(r"\b(animation|transition)\s*:", css):
        rep.err(where, "页面自带 CSS 动画/过渡，相机动效必须由渲染器控制")
    if re.search(r"\d+(vw|vh)\b", css):
        rep.err(where, "使用了 vw/vh 单位，破坏坐标稳定性")
    if re.search(r"(?:linear|radial|conic)-gradient\s*\(", css, re.I):
        rep.err(where, "幻灯片使用了渐变，Anthropic 学术风要求平面纯色")
    if re.search(r"(?:box-shadow|text-shadow)\s*:", css, re.I):
        rep.err(where, "幻灯片使用了 shadow，Anthropic 学术风禁止阴影")
    if re.search(r"(?:backdrop-filter|filter)\s*:[^;}]*(?:blur|drop-shadow)", css, re.I):
        rep.err(where, "幻灯片使用了 blur/drop-shadow，Anthropic 学术风禁止模糊/发光")
    for m in re.finditer(r"font-weight\s*:\s*(\d+)", css):
        if int(m.group(1)) > 500:
            rep.err(where, f"存在 font-weight:{m.group(1)}；学术风只允许 400/500")
            break
    if re.search(r"font\s*:[^;}]*\b(?:600|700|800|900)\b", css):
        rep.err(where, "font shorthand 使用了 >500 字重；学术风只允许 400/500")

    for m in re.finditer(r"font-size\s*:\s*([\d.]+)px", css):
        if float(m.group(1)) < 14:
            rep.warn(where, f"存在 font-size:{m.group(1)}px，小于 14px，PPT 全览可读性偏低")
            break

    if p.top_level_blocks > 10:
        rep.err(where, f"顶层内容块 {p.top_level_blocks} 个，超过 v2 严格上限 10；请重构为主视觉而不是继续堆块")
    elif slide.get("role") == "content" and p.top_level_blocks > 8:
        rep.warn(where, f"content 页顶层内容块 {p.top_level_blocks} 个，超过建议上限 8")

    if not p.visuals:
        rep.err(where, "页面没有 data-visual 主视觉对象；v2 禁止纯文字页")
    for v in p.visuals:
        if v["type"] not in ALLOWED_VISUAL_TYPES:
            rep.warn(where, f"data-visual={v['type']!r} 不在推荐视觉类型集合中")
    if p.svg_text_missing_class:
        rep.err(where, f"有 {len(p.svg_text_missing_class)} 个 SVG <text> 未带 t/ts/th/tn 类")

    text_n = p.visible_text_len
    if slide.get("role") == "content":
        if text_n > SLIDE_TEXT_MAX:
            rep.err(where, f"可见文字约 {text_n} 单位，超过正文页严格上限 {SLIDE_TEXT_MAX}；把解释移入 panel 并改成图形关系")
        elif text_n > SLIDE_TEXT_WARN:
            rep.warn(where, f"可见文字约 {text_n} 单位，超过建议目标 {SLIDE_TEXT_WARN}")
    elif text_n > 125:
        rep.warn(where, f"首尾页可见文字约 {text_n} 单位，建议继续压缩")

    for dup in p.duplicate_anchor_ids:
        rep.err(where, f"HTML 内 data-anchor={dup!r} 重复")

    return p


def validate_anchors(slide: dict, parser: SlideParser, rep: Report, global_ids: dict) -> None:
    where = slide["id"]
    seen: set[str] = set()
    rects: list[tuple[str, dict]] = []

    for anchor in slide["anchors"]:
        aid, rect = anchor["id"], anchor["rect"]
        if not ANCHOR_ID_RE.match(aid):
            rep.err(where, f"锚点 id {aid!r} 不符合 ^[a-z][a-z0-9-]{{1,39}}$")
        if aid in seen:
            rep.err(where, f"lecture.json 内锚点 id {aid!r} 重复")
        seen.add(aid)
        if aid in global_ids and global_ids[aid] != slide["id"]:
            rep.err(where, f"锚点 id {aid!r} 与 {global_ids[aid]} 页重名（需全 deck 唯一）")
        global_ids.setdefault(aid, slide["id"])

        if rect["x"] + rect["w"] > CANVAS_W or rect["y"] + rect["h"] > CANVAS_H:
            rep.err(where, f"锚点 {aid} 的 rect 超出画布：{rect}")

        html_anchor = parser.anchors.get(aid)
        if html_anchor is None:
            rep.err(where, f"HTML 中找不到 data-anchor=\"{aid}\"")
            continue

        raw = html_anchor["data-rect"]
        if not raw:
            rep.err(where, f"锚点 {aid} 的 HTML 元素缺少 data-rect")
        else:
            m = RECT_RE.match(raw)
            if not m:
                rep.err(where, f"锚点 {aid} 的 data-rect={raw!r} 格式应为 \"x y w h\"")
            else:
                hx, hy, hw, hh = (int(g) for g in m.groups())
                if (hx, hy, hw, hh) != (rect["x"], rect["y"], rect["w"], rect["h"]):
                    rep.err(
                        where,
                        f"锚点 {aid} 的 data-rect=({hx},{hy},{hw},{hh}) "
                        f"与 lecture.json 的 ({rect['x']},{rect['y']},{rect['w']},{rect['h']}) 不一致",
                    )

        inline = parse_inline_px(html_anchor["style"])
        pairs = (("left", "x"), ("top", "y"), ("width", "w"), ("height", "h"))
        missing = [css_prop for css_prop, _ in pairs if css_prop not in inline]
        if missing == ["height"]:
            rep.warn(
                where,
                f"锚点 {aid} 内联样式未写 height，实际高度依赖内容；"
                "建议跑 measure_anchors.py 用浏览器回填真实矩形",
            )
        elif missing:
            rep.err(where, f"锚点 {aid} 内联样式缺少 {', '.join(missing)}，无法静态校验坐标")
        for css_prop, key in pairs:
            if css_prop in inline and abs(inline[css_prop] - rect[key]) > 0.5:
                rep.err(
                    where,
                    f"锚点 {aid} 内联 {css_prop}:{inline[css_prop]:g}px "
                    f"与 rect.{key}={rect[key]} 不一致",
                )

        if rect["w"] < MIN_ANCHOR_W or rect["h"] < MIN_ANCHOR_H:
            rep.warn(
                where,
                f"锚点 {aid} 尺寸 {rect['w']}×{rect['h']} 小于建议下限 "
                f"{MIN_ANCHOR_W}×{MIN_ANCHOR_H}，放大后周围会大量留白",
            )

        rects.append((aid, rect))

    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            (ida, ra), (idb, rb) = rects[i], rects[j]
            if rects_overlap(ra, rb):
                rep.warn(where, f"锚点 {ida} 与 {idb} 矩形重叠")
            elif rects_overlap(ra, rb, gap=ANCHOR_GAP):
                rep.warn(where, f"锚点 {ida} 与 {idb} 间距小于 {ANCHOR_GAP}px，高亮描边会压边")

    for aid in parser.anchors:
        if aid not in seen:
            rep.warn(where, f"HTML 中的 data-anchor=\"{aid}\" 未在 lecture.json 里声明，讲解不会用到")


PANEL_FORBIDDEN = [
    (re.compile(r"```"), "代码块"),
    (re.compile(r"^\s*\|.*\|\s*$", re.M), "表格"),
    (re.compile(r"!\[[^\]]*\]\("), "图片"),
    (re.compile(r"<[a-zA-Z/][^>]*>"), "HTML 标签"),
    (re.compile(r"\$\$|\\\[|\\begin\{"), "LaTeX 公式块"),
]


def validate_steps(slide: dict, rep: Report, defaults: dict, global_step_ids: set) -> int:
    where = slide["id"]
    anchors = {a["id"]: a for a in slide["anchors"]}
    steps = slide["steps"]
    zoom_count = 0

    d_cam = defaults.get("camera", {})
    default_depth = d_cam.get("depth")
    default_padding = d_cam.get("padding", DEFAULT_PADDING)

    orders = [s["order"] for s in steps]
    if orders != list(range(1, len(steps) + 1)):
        rep.err(where, f"steps 的 order 必须从 1 连续递增，实际为 {orders}")

    for step in steps:
        sid = step["id"]
        tag = f"{where}/{sid}"
        if not STEP_ID_RE.match(sid):
            rep.err(tag, "step id 不符合 ^s\\d{2}-\\d{2}$")
        if not sid.startswith(where + "-"):
            rep.err(tag, f"step id 前缀应为 {where}-")
        if sid in global_step_ids:
            rep.err(tag, "step id 全 deck 重复")
        global_step_ids.add(sid)

        if step.get("advance") != "manual":
            rep.err(tag, "advance 必须为 'manual'（本版本纯步骤驱动）")

        camera = step["camera"]
        kind = step["kind"]

        if kind == "overview":
            if camera.get("mode") != "fit":
                rep.err(tag, "overview 步的 camera.mode 必须为 'fit'")
            if any(k in camera for k in ("anchorId", "depth", "scale", "focus")):
                rep.err(tag, "overview 步不得携带 anchorId/depth/scale/focus")
            continue

        zoom_count += 1
        if camera.get("mode") != "anchor":
            rep.err(tag, "zoom 步的 camera.mode 必须为 'anchor'")
            continue
        aid = camera.get("anchorId")
        if aid not in anchors:
            rep.err(tag, f"camera.anchorId={aid!r} 不在本页 anchors 中")
            continue
        if "depth" in camera and "scale" in camera:
            rep.err(tag, "depth 与 scale 只能二选一")

        rect = anchors[aid]["rect"]
        s = resolve_scale(camera, rect, default_depth, default_padding)
        if s <= MIN_SCALE + 1e-6:
            rep.warn(tag, f"解出的放大倍率 {s:.2f} 接近 1，锚点过大，建议改用 overview 步")

        if "focus" in camera:
            cx, cy = camera["focus"]["cx"], camera["focus"]["cy"]
            if not (0 <= cx <= 1 and 0 <= cy <= 1):
                rep.err(tag, f"focus 必须位于归一化画布 0..1，实际 cx={cx}, cy={cy}")
            acx, acy = rect_center_focus(rect)
            if abs(cx - acx) > 0.25 or abs(cy - acy) > 0.25:
                rep.warn(tag, "focus 与锚点中心偏离超过 25% 画布，确认是有意为之")

        panel = step.get("panel")
        if not panel:
            rep.err(tag, "zoom 步必须带 panel")
        else:
            body = panel["body"]
            n = cjk_len(body)
            if n < PANEL_MIN_CHARS:
                rep.warn(tag, f"小窗正文约 {n} 字，短于教授式讲解建议下限 {PANEL_MIN_CHARS}")
            elif n > PANEL_MAX_CHARS:
                rep.warn(tag, f"小窗正文约 {n} 字，超过教授式讲解建议上限 {PANEL_MAX_CHARS}；请拆 step")
            title = panel.get("title", "")
            if cjk_len(title) > 20:
                rep.warn(tag, "panel.title 过长；小窗标题应像课堂提示，不像第二个页标题")
            for phrase in AIISH_PANEL_PHRASES:
                if phrase in body:
                    rep.warn(tag, f"小窗出现偏 AI/读稿腔表达 {phrase!r}，请改成自然教授口吻")
                    break
            sentences = [x.strip() for x in re.split(r"[。！？!?]", re.sub(r"[`*_>#\-\[\]()]", "", body)) if x.strip()]
            if any(cjk_len(x) > 42 for x in sentences):
                rep.warn(tag, "小窗存在过长单句（>42 等价单位），建议拆成更自然的课堂短句")
            list_items = len(re.findall(r"^\s*(?:[-*]|\d+[.)])\s+", body, re.M))
            if list_items > 3:
                rep.warn(tag, f"小窗有 {list_items} 个列表项；教授式讲解默认最多 3 条")
            narration = step.get("narration")
            if narration and re.sub(r"\s+", "", narration) == re.sub(r"\s+", "", body):
                rep.warn(tag, "narration 与 panel.body 完全相同，像逐字读稿；两者应有口语差异")
            for pattern, label in PANEL_FORBIDDEN:
                if pattern.search(body):
                    rep.warn(tag, f"小窗正文含{label}，渲染器只保证富文本子集，会被降级为纯文本")
            for avoid in panel.get("avoidAnchorIds", []):
                if avoid not in anchors:
                    rep.err(tag, f"panel.avoidAnchorIds 引用了本页不存在的锚点 {avoid!r}")

        for hid in step.get("highlight", {}).get("anchorIds", []):
            if hid not in anchors:
                rep.err(tag, f"highlight.anchorIds 引用了本页不存在的锚点 {hid!r}")

    return zoom_count


def validate(project_dir: str, rep: Report) -> dict:
    lecture_path = os.path.join(project_dir, "lecture.json")
    with open(lecture_path, encoding="utf-8") as fh:
        data = json.load(fh)

    if data.get("schemaVersion") != SCHEMA_VERSION:
        rep.err("lecture.json", f"schemaVersion 必须为 {SCHEMA_VERSION!r}")

    validate_json_schema(data, rep)

    deck = data.get("deck", {})
    defaults = data.get("defaults", {})
    slides = data.get("slides", [])
    if not slides:
        rep.err("lecture.json", "slides 为空")
        return {"slideCount": 0, "contentSlideCount": 0, "stepCount": 0}
    if len(slides) < 3:
        rep.err("lecture.json", "v2 至少需要 3 页：opening + content + closing")
    roles = [s.get("role") for s in slides]
    if slides and roles[0] != "opening":
        rep.err("lecture.json", "第一页 role 必须为 opening")
    if slides and roles[-1] != "closing":
        rep.err("lecture.json", "最后一页 role 必须为 closing")
    for i, role in enumerate(roles[1:-1], start=2):
        if role != "content":
            rep.err("lecture.json", f"第 {i} 页 role 必须为 content，实际为 {role!r}")

    indices = [s.get("index") for s in slides]
    if indices != list(range(1, len(slides) + 1)):
        rep.err("lecture.json", f"slides[].index 必须从 1 连续递增，实际为 {indices}")

    slide_dir = deck.get("slideDir", "slides")
    global_anchor_ids: dict[str, str] = {}
    global_step_ids: set[str] = set()
    total_steps = 0

    seen_slide_ids: set[str] = set()
    for slide in slides:
        sid = slide.get("id", "?")
        if not SLIDE_ID_RE.match(str(sid)):
            rep.err(str(sid), "slide id 不符合 ^s\\d{2}$")
        if sid in seen_slide_ids:
            rep.err(str(sid), "slide id 重复")
        seen_slide_ids.add(sid)

        rel = slide.get("file", "")
        expected_prefix = slide_dir.rstrip("/") + "/"
        if not rel.startswith(expected_prefix):
            rep.warn(str(sid), f"file={rel!r} 不在 deck.slideDir={slide_dir!r} 目录下")
        path = os.path.join(project_dir, rel)
        if not os.path.isfile(path):
            rep.err(str(sid), f"幻灯片文件不存在：{rel}")
            continue

        parser = validate_slide_html(path, slide, rep)
        if parser is None:
            continue
        validate_anchors(slide, parser, rep, global_anchor_ids)
        zoom_count = validate_steps(slide, rep, defaults, global_step_ids)
        total_steps += len(slide["steps"])
        role = slide.get("role")
        steps = slide.get("steps", [])
        if not steps or steps[0].get("kind") != "overview":
            rep.err(str(sid), f"{role} 页必须以 overview step 起手")
        if role == "opening":
            if len(steps) != 1 or zoom_count != 0:
                rep.err(str(sid), "opening 页应只有 1 个 overview step，不做局部 zoom")
        elif role == "content":
            if zoom_count < 2:
                rep.err(str(sid), f"content 页只有 {zoom_count} 个 zoom；v2 要求 2–4 个视觉讲解点")
            elif zoom_count > 4:
                rep.err(str(sid), f"content 页有 {zoom_count} 个 zoom，超过严格上限 4；请拆页")
        elif role == "closing" and zoom_count > 2:
            rep.err(str(sid), f"closing 页有 {zoom_count} 个 zoom，收束页最多 2 个")

    orphan_files = []
    abs_slide_dir = os.path.join(project_dir, slide_dir)
    if os.path.isdir(abs_slide_dir):
        declared = {os.path.basename(s.get("file", "")) for s in slides}
        for name in sorted(os.listdir(abs_slide_dir)):
            if name.endswith(".html") and name not in declared:
                orphan_files.append(name)
    for name in orphan_files:
        rep.warn(slide_dir, f"存在未被 lecture.json 引用的页面文件 {name}")

    runtime_path = os.path.join(project_dir, "runtime", "index.html")
    if not os.path.isfile(runtime_path):
        rep.err("runtime", "缺少 runtime/index.html；v2 标准交付必须包含运行时")
    else:
        try:
            runtime_html = open(runtime_path, encoding="utf-8").read()
            for marker, label in [
                ("perspective:", "3D perspective"),
                ("spatial-layer", "Spatial UI 独立空间层"),
                ("interaction-layer", "用户自由查看独立层"),
                ("rotateY", "侧向纸面旋转"),
                ("rotateX", "纵向纸面旋转"),
                ("translate3d", "Z-depth 空间位移"),
                ("addEventListener('wheel'", "滚轮自由缩放"),
                ("addEventListener('pointerdown'", "左键拖拽自由查看"),
                ("resetUserView", "自动镜头接管与自由视角复位"),
                ("reveal-token", "小窗柔和文字显现"),
                ("class=\"onboarding\"", "首次蓝色操作提示窗"),
                ("geometry-probe-fit", "3D 几何测量探针"),
                ("focusRectForStep", "camera/highlight 联合保护区域"),
                ("fitCameraToSafeArea", "protected-view 镜头求解"),
                ("finalProtectedGuard", "动画落定后的完整性二次保护"),
                ("protectedRect", "panel 安全区计算"),
                ("placementOrder", "panel 自动换边候选"),
                ("--outside:#ffffff", "纸面外纯白背景"),
                ("ZOOM_BUNDLE_START", "单文件 bundle 注入点"),
                ("frame.srcdoc", "内嵌 slide 加载"),
                ("../lecture.json", "开发态 lecture.json 加载"),
                (".viewport{position:absolute;inset:0", "full-bleed viewport"),
            ]:
                if marker not in runtime_html:
                    rep.warn("runtime", f"运行时缺少标准特征：{label}")
            for forbidden, label in [
                ("class=\"topbar\"", "顶部放映器栏"),
                ("class=\"controls\"", "底部控制栏"),
                ("view-indicator", "FREE VIEW zoom 状态标签"),
                ("class=\"status\"", "debug 状态标签"),
                ("先按自己的节奏看", "拟人化 onboarding 长文"),
                ("切到下一讲时，镜头会自然接回", "解释性 onboarding 长文"),
                ("明白，开始", "旧版对话式 onboarding 按钮"),
            ]:
                if forbidden in runtime_html:
                    rep.err("runtime", f"v2.3 纯净运行时禁止出现：{label}")
        except OSError as exc:
            rep.err("runtime", f"读取 runtime/index.html 失败：{exc}")

    standalone_path = os.path.join(project_dir, "dist", "lecture.html")
    if not os.path.isfile(standalone_path):
        rep.err("standalone", "缺少 dist/lecture.html；v2.3 标准交付必须生成单文件离线发布物")
    else:
        try:
            standalone_html = open(standalone_path, encoding="utf-8").read()
            for marker, label in [
                ('data-zoom-standalone="true"', "standalone 构建标记"),
                ('"format":"zoom-lecture-standalone/v1"', "内嵌 bundle"),
                ('id="zoomLectureBundle"', "内嵌 lecture 数据"),
                ('frame.srcdoc', "srcdoc slide 加载"),
                ('fitCameraToSafeArea', "protected-view 镜头求解"),
                ('finalProtectedGuard', "完整性二次保护"),
                ('geometry-probe-fit', "3D 几何测量探针"),
            ]:
                if marker not in standalone_html:
                    rep.err("standalone", f"单文件发布物缺少：{label}")
            if '>null</script><!-- ZOOM_BUNDLE_END -->' in standalone_html:
                rep.err("standalone", "bundle 仍为 null；似乎没有执行 build_standalone.py")
        except OSError as exc:
            rep.err("standalone", f"读取 dist/lecture.html 失败：{exc}")

    return {
        "slideCount": len(slides),
        "contentSlideCount": sum(1 for s in slides if s.get("role") == "content"),
        "stepCount": total_steps,
    }


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="校验 interactive-lecture-deck 工程")
    ap.add_argument("project_dir")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--strict", action="store_true", help="WARNING 也判为失败")
    args = ap.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    if not os.path.isdir(project_dir):
        print(f"[用法错误] 目录不存在: {project_dir}", file=sys.stderr)
        return 2
    if not os.path.isfile(os.path.join(project_dir, "lecture.json")):
        print(f"[用法错误] 找不到 {project_dir}/lecture.json", file=sys.stderr)
        return 2

    rep = Report()
    try:
        stats = validate(project_dir, rep)
    except json.JSONDecodeError as exc:
        print(f"[读取错误] lecture.json 不是合法 JSON: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(
            json.dumps(
                {
                    "status": rep.status,
                    "errors": rep.errors,
                    "warnings": rep.warnings,
                    **stats,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for e in rep.errors:
            print(f"ERROR   {e}")
        for w in rep.warnings:
            print(f"WARNING {w}")
        print(
            f"\n{rep.status.upper()}  "
            f"slides={stats.get('slideCount', 0)} content={stats.get('contentSlideCount', 0)} steps={stats.get('stepCount', 0)} "
            f"errors={len(rep.errors)} warnings={len(rep.warnings)}"
        )

    if rep.errors:
        return 1
    if args.strict and rep.warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
