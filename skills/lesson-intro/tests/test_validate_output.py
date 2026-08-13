import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("lesson_intro_validator", ROOT / "scripts" / "validate_output.py")
validator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validator)


class LessonIntroValidatorTests(unittest.TestCase):
    def setUp(self):
        self.html = (ROOT / "assets" / "example-page.html").read_text(encoding="utf-8")

    def test_direct_example_page_validates(self):
        validator.validate_input(self.html)

    def test_removed_research_envelope_is_rejected(self):
        with self.assertRaises(ValueError):
            validator.validate_envelope({
                "html": self.html,
                "structured_data": {
                    "research": {"claims": [], "sources": []}
                },
            })

    def test_removed_visible_citations_field_is_rejected(self):
        with self.assertRaises(ValueError):
            validator.validate_envelope({"html": self.html, "visible_citations": True})

    def test_visual_contract_rejects_heavy_card_style(self):
        bad = self.html.replace("<style>", "<style>main{border-radius:24px}", 1)
        with self.assertRaises(ValueError):
            validator.validate_html(bad)

    def test_visual_contract_rejects_unclassed_svg_text(self):
        bad = self.html.replace('<text class="th"', '<text', 1)
        with self.assertRaises(ValueError):
            validator.validate_html(bad)


if __name__ == "__main__":
    unittest.main()
