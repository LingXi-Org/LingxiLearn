import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "evaluate.py"
SPEC = importlib.util.spec_from_file_location("evaluate", MODULE_PATH)
evaluate = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(evaluate)


class EvalHarnessTests(unittest.TestCase):
    def setUp(self):
        self.run = json.loads((ROOT / "assets" / "example-run.json").read_text(encoding="utf-8"))

    def test_example_run_validates(self):
        evaluate.validate_run(self.run)

    def test_example_run_passes(self):
        report = evaluate.evaluate(self.run)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["summary"]["failed_cases"], 0)

    def test_duplicate_question_is_reported(self):
        bad = json.loads(json.dumps(self.run))
        bad["cases"][0]["trajectory"]["turns"].append({"question_id": "q1", "new_evidence": False})
        bad["cases"][0]["trajectory"]["turns"].append({"question_id": "q1", "new_evidence": False})
        report = evaluate.evaluate(bad)
        findings = report["cases"][0]["layers"]["trajectory"]["findings"]
        self.assertTrue(any(item["check_id"] == "trajectory.repeated_question" and item["status"] == "fail" for item in findings))

    def test_leakage_is_reported(self):
        bad = json.loads(json.dumps(self.run))
        bad["cases"][0]["expectations"]["answer_tokens"] = ["42"]
        bad["cases"][0]["output"]["student_response"]["text"] = "答案是 42。"
        report = evaluate.evaluate(bad)
        findings = report["cases"][0]["layers"]["pedagogy"]["findings"]
        self.assertTrue(any(item["check_id"] == "pedagogy.answer_leakage" and item["status"] == "fail" for item in findings))

    def test_formative_assessor_validator_passes(self):
        path = ROOT.parent / "formative-assessor" / "assets" / "eval-run.json"
        run = json.loads(path.read_text(encoding="utf-8"))
        run["skill_path"] = str(ROOT.parent / "formative-assessor")
        report = evaluate.evaluate(run)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["summary"]["case_count"], 2)

    def test_retrieval_builder_validator_passes(self):
        path = ROOT.parent / "retrieval-practice-builder" / "assets" / "eval-run.json"
        run = json.loads(path.read_text(encoding="utf-8"))
        run["skill_path"] = str(ROOT.parent / "retrieval-practice-builder")
        report = evaluate.evaluate(run)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["summary"]["case_count"], 2)

    def test_retrieval_public_task_cannot_contain_assumptions(self):
        path = ROOT.parent / "retrieval-practice-builder" / "assets" / "eval-run.json"
        run = json.loads(path.read_text(encoding="utf-8"))
        run["cases"][0]["output"]["public_task"]["assumptions"] = ["hidden fact"]
        report = evaluate.evaluate(run)
        findings = report["cases"][0]["layers"]["component"]["findings"]
        self.assertTrue(any(item["check_id"] == "component.public_task_safe" and item["status"] == "fail" for item in findings))

    def test_required_layer_cannot_be_missing(self):
        bad = json.loads(json.dumps(self.run))
        bad["cases"][0]["expectations"]["required_layers"] = ["learner_outcome"]
        bad["cases"][0].pop("outcome")
        report = evaluate.evaluate(bad)
        self.assertEqual(report["status"], "fail")
        findings = report["cases"][0]["layers"]["learner_outcome"]["findings"]
        self.assertTrue(any(item["check_id"] == "coverage.required_layer" for item in findings))


if __name__ == "__main__":
    unittest.main()
