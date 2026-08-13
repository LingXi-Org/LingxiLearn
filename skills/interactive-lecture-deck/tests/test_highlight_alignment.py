from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[3]
RUNTIME_FILES = (
    ROOT / "skills/interactive-lecture-deck/assets/runtime/index.html",
    ROOT / "skills/interactive-lecture-deck/assets/examples/quadratic-vertex/runtime/index.html",
    ROOT / "skills/interactive-lecture-deck/assets/examples/quadratic-vertex/dist/lecture.html",
)


def test_highlight_and_probe_are_coplanar_with_slide_frame():
    for path in RUNTIME_FILES:
        text = path.read_text(encoding="utf-8")
        assert re.search(r"\.slide-frame\{[^}]*transform:translateZ\(0\)", text)
        assert re.search(r"\.highlight-layer\{[^}]*transform:translateZ\(0\)", text)
        assert re.search(r"\.geometry-probe-anchor\{[^}]*transform:translateZ\(0\)", text)
        assert not re.search(r"\.highlight-layer\{[^}]*translateZ\(2px\)", text)


def test_render_discards_stale_page_loads_before_painting_highlights():
    """A slow iframe load must not let an older step paint over a newer step."""
    for path in RUNTIME_FILES:
        text = path.read_text(encoding="utf-8")
        assert "loadedSlideId=null,pendingSlideLoad=null" in text
        assert "pendingSlideLoad?.cancel?.()" in text
        assert "const run=++renderRun" in text
        assert "if(run!==renderRun||cursor!==targetCursor)return" in text
