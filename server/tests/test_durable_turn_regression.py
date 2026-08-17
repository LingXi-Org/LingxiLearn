from lingxilearn.runtime.completion import CompletionContext, evaluate
from lingxilearn.runtime.contracts import CandidateAction, DoneCondition
from lingxilearn.runtime.orchestrator import _default_done_condition


def test_provider_result_is_host_completion_fact_not_fake_evidence() -> None:
    condition = DoneCondition(kind="provider_result")
    assert evaluate(condition, CompletionContext(provider_result=True)).satisfied
    assert not evaluate(condition, CompletionContext(provider_result=False)).satisfied


def test_structural_capabilities_default_to_provider_result() -> None:
    candidate = CandidateAction(
        candidate_id="candidate_prereq",
        capability="graph.prerequisite",
        skill_id="prerequisite-analyzer",
        provider="prerequisite_analyzer",
    )
    condition = _default_done_condition(candidate)
    assert condition.kind == "provider_result"
    assert condition.signal == ""
