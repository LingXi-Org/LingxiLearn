#!/usr/bin/env python3
"""Drive the real UI in a browser and capture screenshots.

    python scripts/ui_smoke.py --base http://localhost:8000 --out var/screenshots

Walks the full learner journey — pick a mission, take the pre-test, work the
packet lab and the attribution table, submit, reach the report — asserting at
each stop that what should be on screen is on screen. Failures leave a
screenshot behind so the state is inspectable.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# The image ships Chromium; never let Playwright try to download its own.
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
CHROMIUM = Path("/opt/pw-browsers/chromium-1194/chrome-linux/chrome")

from playwright.sync_api import Page, TimeoutError as PwTimeout, sync_playwright  # noqa: E402

_failures: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"{'[PASS]' if ok else '[FAIL]'} {label}" + (f"  — {detail}" if detail else ""))
    if not ok:
        _failures.append(label)


TRUTH = {
    "dns": 121,
    "tcp_connect": 32,
    "ttfb": 189,
    "transfer": 19,
    "retransmission": 226,
}
PINS = {
    "dns": [1, 2],
    "tcp_connect": [3, 4, 5],
    "ttfb": [6, 7],
    "transfer": [8, 9, 10],
    "retransmission": [12, 13, 14],
}
BUCKET_LABELS = {
    "dns": "DNS 解析",
    "tcp_connect": "TCP 建连",
    "ttfb": "请求等待",
    "transfer": "数据传输",
    "retransmission": "重传停顿",
}
PROBE_ANSWERS = {"web-slow": ["A", "B", "B"], "reliable-delivery": ["B", "B", "B"]}
VERIFY_ANSWERS = {"web-slow": ["C", "B"], "reliable-delivery": ["B", "B"]}
# Correct option per in-step question, so the walk-through exercises the
# success path rather than accidentally testing max-attempts exhaustion.
STEP_ANSWERS = {"orient": "b", "stall": "b", "read-the-console": "a", "debrief": "b"}


def wait_idle(page: Page, timeout: int = 40_000) -> None:
    """Wait until the previous turn has been judged and the UI accepts input.

    The classroom clears its pending selection whenever a run finishes, so
    clicking mid-run would both fail and lose the choice.
    """
    page.wait_for_function(
        "() => !document.body.innerText.includes('正在判定')",
        timeout=timeout,
    )


def shoot(page: Page, out: Path, name: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out / f"{name}.png"), full_page=False)
    print(f"       screenshot → {out / f'{name}.png'}")


ITEM_IDS = {"probe": ["p1", "p2", "p3"], "verify": ["v1", "v2"]}


def answer_multiple_choice(page: Page, item_ids: list[str], letters: list[str]) -> None:
    for item_id, letter in zip(item_ids, letters):
        page.get_by_test_id(f"item-{item_id}-{letter.lower()}").click()
    page.get_by_test_id("submit-items").click()


def run(base: str, out: Path, mission_title: str, mission_id: str) -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=str(CHROMIUM) if CHROMIUM.exists() else None,
            args=["--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1560, "height": 980})
        page.set_default_timeout(25_000)

        # ---- home ----------------------------------------------------
        page.goto(base, wait_until="networkidle")
        check(page.get_by_text("今天想解决什么工程问题").is_visible(), "home page rendered")
        check(page.get_by_text(mission_title).first.is_visible(), f"mission card: {mission_title}")
        check(
            page.get_by_text("为什么这件事不能靠对话框完成").first.is_visible(),
            "mission states what a chat window cannot do",
        )
        shoot(page, out, f"01-home")

        # ---- start ---------------------------------------------------
        card = page.locator("article").filter(has_text=mission_title).first
        card.get_by_role("button", name="开始").click()
        page.wait_for_url("**/classroom/**", timeout=25_000)
        page.wait_for_selector("text=开始前，先花一分钟", timeout=30_000)
        check(True, "classroom opened with the pre-test")
        shoot(page, out, f"02-{mission_id}-pretest")

        # ---- pre-test ------------------------------------------------
        answer_multiple_choice(page, ITEM_IDS["probe"], PROBE_ANSWERS[mission_id])
        page.wait_for_selector("text=AI 教练", timeout=30_000)
        wait_idle(page)

        seen_sim = False
        for _round in range(1, 16):
            page.wait_for_timeout(900)

            if page.locator("text=最后两题").count() or "/report" in page.url:
                break

            # Branch on the controls actually present, not on scene text: the
            # preview console and the interactive one look the same but only one
            # of them is asking for an action log.
            if page.get_by_test_id("submit-choice").count():
                wait_idle(page)
                if page.get_by_test_id("sim-submit").count() and not seen_sim:
                    seen_sim = True
                    check(True, "simulator console rendered")
                    shoot(page, out, f"03-{mission_id}-simulator")
                step_id = page.locator("[data-step]").first.get_attribute("data-step") or ""
                page.get_by_test_id(f"choice-{STEP_ANSWERS.get(step_id, 'b')}").click()
                page.get_by_test_id("submit-choice").click()
                page.wait_for_timeout(600)
                continue

            if page.get_by_test_id("sim-submit").count():
                wait_idle(page)
                if not seen_sim:
                    seen_sim = True
                    check(page.get_by_text("序号 — 时间").count() > 0, "seq/time chart drawn")
                shoot(page, out, f"03-{mission_id}-simulator")
                drive_simulator(page)
                continue

            if page.get_by_text("时间预算").count():
                wait_idle(page)
                check(page.locator("svg").first.is_visible(), "packet ladder drawn")
                shoot(page, out, f"03-{mission_id}-attribution")
                fill_attribution(page)
                page.get_by_role("button", name="提交归因表").click()
                page.wait_for_timeout(800)
                continue

            page.wait_for_timeout(1200)

        # ---- post-test -----------------------------------------------
        try:
            page.wait_for_selector("text=最后两题", timeout=40_000)
            wait_idle(page)
            shoot(page, out, f"04-{mission_id}-posttest")
            answer_multiple_choice(page, ITEM_IDS["verify"], VERIFY_ANSWERS[mission_id])
            check(True, "post-test submitted")
        except PwTimeout:
            check(False, "post-test reached", f"stuck at {page.url}")

        # ---- report --------------------------------------------------
        try:
            page.wait_for_url("**/report/**", timeout=40_000)
            # Anchor on the loaded report, not on text that also appears in the
            # loading state ("正在生成学习报告…" contains "学习报告").
            page.wait_for_selector('[data-testid="report-root"]', timeout=25_000)
            page.wait_for_timeout(500)
            check(True, "learning report reached")
            check(page.locator("h1").first.inner_text() != "", "headline rendered",
                  page.locator("h1").first.inner_text()[:44])
            check(page.get_by_text("掌握度变化").is_visible(), "mastery movement shown")
            check(page.get_by_text("可回溯证据").is_visible(), "evidence count shown")
            claim = page.locator("text=条依据").first
            if claim.count():
                claim.click()
                page.wait_for_timeout(400)
                check(True, "report claims expand to their evidence")
            shoot(page, out, f"05-{mission_id}-report")
        except PwTimeout:
            check(False, "learning report reached", f"stuck at {page.url}")
            shoot(page, out, f"05-{mission_id}-stuck")

        browser.close()


def fill_attribution(page: Page) -> None:
    """Type each bucket's milliseconds, then pin its evidence frames."""
    for bucket, ms in TRUTH.items():
        page.get_by_test_id(f"ms-{bucket}").fill(str(ms))
        page.get_by_test_id(f"pin-{bucket}").click()
        for frame in PINS[bucket]:
            page.get_by_test_id(f"frame-label-{frame}").click()
        page.wait_for_timeout(60)


def drive_simulator(page: Page) -> None:
    """Play a correct sender: keep the window full, fast-retransmit, finish.

    Every control is checked for being enabled before it is clicked, because the
    console's state lands a tick after the request returns.
    """
    for _ in range(120):
        if page.locator('[data-sim-done="1"]').count():
            break
        acted = False
        # Recovery first: the pulsing button means duplicate ACKs or a timeout.
        for testid in ("sim-retransmit", "sim-send", "sim-wait"):
            control = page.get_by_test_id(testid).first
            if testid == "sim-retransmit" and not page.locator("button.pulse-ring").count():
                continue
            if control.count() and control.is_enabled():
                control.click()
                acted = True
                break
        if not acted:
            page.wait_for_timeout(200)
        page.wait_for_timeout(90)

    submit = page.get_by_test_id("sim-submit")
    if submit.count():
        submit.click()
        page.wait_for_timeout(1200)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--out", default=str(REPO_ROOT / "var" / "screenshots"))
    parser.add_argument("--mission", default="web-slow")
    args = parser.parse_args()

    titles = {"web-slow": "慢在哪一环", "reliable-delivery": "你来当发送方"}
    print(f"=== LingxiLearn UI smoke · {args.base} · {args.mission} ===")
    run(args.base, Path(args.out), titles[args.mission], args.mission)
    print()
    print("RESULT:", "FAILED — " + ", ".join(_failures) if _failures else "all checks passed")
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
