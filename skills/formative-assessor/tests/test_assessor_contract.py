import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("assessor_contract", ROOT / "scripts" / "assessor_contract.py")
assessor = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(assessor)


class AssessorContractTests(unittest.TestCase):
    def setUp(self):
        self.task = json.loads((ROOT / "assets" / "example-task.json").read_text(encoding="utf-8"))
        self.result = json.loads((ROOT / "assets" / "example-result.json").read_text(encoding="utf-8"))

    def test_pair_validates(self):
        assessor.validate_pair(self.task, self.result)

    def test_inferred_confidence_rejected(self):
        bad = json.loads(json.dumps(self.result))
        bad["confidence_basis"] = "not_provided"
        bad["confidence"] = "high"
        with self.assertRaises(assessor.ContractError):
            assessor.validate_result(bad)

    def test_learner_facing_field_rejected(self):
        bad = json.loads(json.dumps(self.result))
        bad["student_response"] = {"text": "请继续"}
        with self.assertRaises(assessor.ContractError):
            assessor.validate_result(bad)

    def test_foreign_evidence_ref_rejected(self):
        bad = json.loads(json.dumps(self.result))
        bad["evidence_refs"] = ["ev_unknown"]
        with self.assertRaises(assessor.ContractError):
            assessor.validate_pair(self.task, bad)


if __name__ == "__main__":
    unittest.main()
