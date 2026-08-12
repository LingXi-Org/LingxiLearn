import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "quiz_contract.py"
spec = importlib.util.spec_from_file_location("quiz_contract", MODULE_PATH)
quiz_contract = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(quiz_contract)


class QuizContractTests(unittest.TestCase):
    def setUp(self):
        self.example = json.loads((ROOT / "assets" / "example-result.json").read_text(encoding="utf-8"))

    def test_example_input_validates(self):
        value = json.loads((ROOT / "assets" / "example-input.json").read_text(encoding="utf-8"))
        quiz_contract.validate_input(value)

    def test_example_validates(self):
        quiz_contract.validate_result(self.example)

    def test_sanitize_removes_grading_fields(self):
        public = quiz_contract.sanitize_public(self.example)
        self.assertNotIn("assumptions", public)
        for question in public["questions"]:
            self.assertNotIn("answer", question)
            self.assertNotIn("explanation", question)
            self.assertNotIn("keywords", question)

    def test_total_points_mismatch_rejected(self):
        bad = json.loads(json.dumps(self.example))
        bad["total_points"] += 1
        with self.assertRaises(quiz_contract.ContractError):
            quiz_contract.validate_result(bad)


if __name__ == "__main__":
    unittest.main()
