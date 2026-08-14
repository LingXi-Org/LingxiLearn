import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("retrieval_contract", ROOT / "scripts" / "retrieval_contract.py")
retrieval = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(retrieval)


class RetrievalContractTests(unittest.TestCase):
    def setUp(self):
        self.task = json.loads((ROOT / "assets" / "example-task.json").read_text(encoding="utf-8"))
        self.result = json.loads((ROOT / "assets" / "example-result.json").read_text(encoding="utf-8"))

    def test_pair_validates(self):
        retrieval.validate_task(self.task)
        retrieval.validate_result(self.result, self.task)

    def test_blocking_prefetch_rejected(self):
        bad = json.loads(json.dumps(self.result))
        bad["prefetch"]["blocking"] = True
        with self.assertRaises(retrieval.ContractError):
            retrieval.validate_result(bad, self.task)

    def test_public_answer_leakage_rejected(self):
        bad = json.loads(json.dumps(self.result))
        bad["public_task"]["answer"] = "不能"
        with self.assertRaises(retrieval.ContractError):
            retrieval.validate_result(bad, self.task)

    def test_insufficient_evidence_shape(self):
        result = {
            "schema_version": "retrieval-practice-builder-result.v1",
            "task_id": self.task["task_id"],
            "status": "insufficient_evidence",
            "concept": self.task["concept"],
            "candidates": [],
            "selection": None,
            "public_task": None,
            "grading_key": None,
            "validation": {
                "answerable": False,
                "evidence_grounded": False,
                "misconception_checked": False,
                "difficulty_checked": False,
                "public_internal_separated": True
            },
            "prefetch": {"blocking": False, "discard_if": ["证据变化"], "cache_key": "empty"},
            "evidence_refs": self.task["learner_evidence"]["evidence_refs"],
            "warnings": ["材料不足，暂不生成任务。"]
        }
        retrieval.validate_result(result, self.task)


if __name__ == "__main__":
    unittest.main()
