from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace(path: str, old: str, new: str) -> None:
    target = ROOT / path
    source = target.read_text()
    if old not in source:
        raise SystemExit(f"expected snippet not found in {path}: {old[:120]!r}")
    target.write_text(source.replace(old, new, 1))


def append(path: str, text: str) -> None:
    target = ROOT / path
    target.write_text(target.read_text() + text)


# Backend: structural provider results are a completion fact, not fake learning evidence.
replace(
    "server/lingxilearn/runtime/contracts.py",
    '    "evidence_observed",\n    "profile_reaches",',
    '    "evidence_observed",\n    "provider_result",\n    "profile_reaches",',
)
replace(
    "server/lingxilearn/runtime/contracts.py",
    '            case "profile_reaches":\n                return f"{self.knowledge_point_id} 掌握度达到 {self.mastery:.2f}"',
    '            case "provider_result":\n                return "执行者已产生有效结果"\n            case "profile_reaches":\n                return f"{self.knowledge_point_id} 掌握度达到 {self.mastery:.2f}"',
)
replace(
    "server/lingxilearn/runtime/completion.py",
    '    user_replied: bool = False\n    quiz_graded: bool = False',
    '    user_replied: bool = False\n    quiz_graded: bool = False\n    provider_result: bool = False\n    """The provider returned a successful, host-observed result for this task."""',
)
replace(
    "server/lingxilearn/runtime/completion.py",
    '        case "profile_reaches":\n            row = context.profile.get(condition.knowledge_point_id)',
    '        case "provider_result":\n            return Verdict(\n                context.provider_result,\n                "执行者已产生有效结果" if context.provider_result else "执行者尚未产生有效结果",\n            )\n\n        case "profile_reaches":\n            row = context.profile.get(condition.knowledge_point_id)',
)
replace(
    "server/lingxilearn/runtime/dispatch.py",
    '                user_replied=bool(self._deps.user_message.get("message")),\n                quiz_graded="grading" in self._results,',
    '                user_replied=bool(self._deps.user_message.get("message")),\n                quiz_graded="grading" in self._results,\n                provider_result=str(result.status or "completed").casefold()\n                in {"completed", "success", "succeeded", "ok"},',
)

# Planner compatibility: advertise the real predicate and repair legacy provider_result-as-evidence plans.
replace(
    "server/lingxilearn/runtime/orchestrator.py",
    'done_when 可用类型：artifact_exists / artifact_valid / evidence_observed /\nprofile_reaches / user_replied / quiz_graded / always / all_of / any_of。',
    'done_when 可用类型：artifact_exists / artifact_valid / evidence_observed / provider_result /\nprofile_reaches / user_replied / quiz_graded / always / all_of / any_of。',
)
replace(
    "server/lingxilearn/runtime/orchestrator.py",
    '    return DoneCondition(kind="evidence_observed", signal="provider_result")',
    '    return DoneCondition(kind="provider_result")',
)
replace(
    "server/lingxilearn/runtime/orchestrator.py",
    '            raw_done = raw.get("done_when")\n            if isinstance(raw_done, Mapping) and str(raw_done.get("kind")) == "always":',
    '            raw_done = raw.get("done_when")\n            if (\n                isinstance(raw_done, Mapping)\n                and str(raw_done.get("kind")) == "evidence_observed"\n                and str(raw_done.get("signal")) == "provider_result"\n            ):\n                # Older planner prompts encoded a successful provider result as\n                # learning evidence. It is a host execution fact, so normalize\n                # it before validation instead of creating an impossible signal.\n                raw_done = {"kind": "provider_result"}\n            if isinstance(raw_done, Mapping) and str(raw_done.get("kind")) == "always":',
)
replace(
    "server/lingxilearn/runtime/orchestrator.py",
    '        and not world.interview_completed\n        and not any(info(task.capability).opening_conversation for task in tasks)\n    ):',
    '        and not world.interview_completed\n        and not any(info(task.capability).opening_conversation for task in tasks)\n        and not any(\n            info(task.capability).turn_complete and not info(task.capability).opening_conversation\n            for task in tasks\n        )\n    ):',
)

# Teaching text must enter the public assistant stream, not exist only in ProviderResult memory.
replace(
    "server/lingxilearn/agents/providers/teaching.py",
    '    if not text:\n        raise ProviderError("adaptive-pedagogy returned no learner-facing text")\n\n    return ProviderResult(\n        learner_message=text,',
    '    if not text:\n        raise ProviderError("adaptive-pedagogy returned no learner-facing text")\n\n    text, withheld = _guarded(text, context)\n    await _emit_learner_output(\n        context.runtime,\n        "adaptive_pedagogy",\n        text,\n        f"{context.task_id}:adaptive_pedagogy:{context.task.id}",\n    )\n\n    return ProviderResult(\n        learner_message=text,',
)
replace(
    "server/lingxilearn/agents/providers/teaching.py",
    '            "withheld_for_leakage": False,',
    '            "withheld_for_leakage": withheld,',
)

# Frontend: V1 assistant streams must be durable visible blocks, not fallback-only text.
replace(
    "web/lib/lingxi/chat-types.ts",
    '  parentSpanId?: string\n}',
    '  parentSpanId?: string\n  /** Stable V1 text lane identity, used to upsert streamed assistant prose. */\n  streamId?: string\n}',
)
replace(
    "web/lib/lingxi/stream/turn-model.ts",
    'function refreshAssistantText(turn: LingxiV1Turn): void {\n  const parts: string[] = []',
    '''function upsertAssistantTextBlock(\n  turn: LingxiV1Turn,\n  streamId: string,\n  content: string,\n  timestamp?: number\n): void {\n  const index = turn.blocks.findIndex(\n    (block) => block.type === 'text' && block.streamId === streamId\n  )\n  const block: ContentBlock = { type: 'text', content, streamId, timestamp }\n  if (index >= 0) turn.blocks[index] = { ...turn.blocks[index], ...block }\n  else turn.blocks.push(block)\n}\n\nfunction refreshAssistantText(turn: LingxiV1Turn): void {\n  const parts: string[] = []''',
)
replace(
    "web/lib/lingxi/stream/turn-model.ts",
    "      turn.streamText[streamId] = full || buffer + delta\n      refreshAssistantText(turn)",
    "      turn.streamText[streamId] = full || buffer + delta\n      upsertAssistantTextBlock(\n        turn,\n        streamId,\n        turn.streamText[streamId],\n        Date.parse(envelope.ts) || undefined\n      )\n      refreshAssistantText(turn)",
)
replace(
    "web/lib/lingxi/stream/turn-model.ts",
    '          if (tag && !turn.streamText.__question__) {\n            turn.streamText.__question__ = tag\n            refreshAssistantText(turn)\n          }',
    '          if (tag && !turn.streamText.__question__) {\n            turn.streamText.__question__ = tag\n            upsertAssistantTextBlock(\n              turn,\n              "__question__",\n              tag,\n              Date.parse(envelope.ts) || undefined\n            )\n            refreshAssistantText(turn)\n          }',
)
replace(
    "web/lib/lingxi/stream/turn-model.ts",
    '            turn.streamText.__resource__ = [existing, tag].filter(Boolean).join(\'\\n\')\n            refreshAssistantText(turn)',
    '            turn.streamText.__resource__ = [existing, tag].filter(Boolean).join(\'\\n\')\n            upsertAssistantTextBlock(\n              turn,\n              "__resource__",\n              turn.streamText.__resource__,\n              Date.parse(envelope.ts) || undefined\n            )\n            refreshAssistantText(turn)',
)

# Live runtime graph: coalesce refreshes from both V0 and V1 lanes. V1 catch-up means this
# still works behind a proxy that buffers the long-lived SSE response.
replace(
    "web/app/workspace/[workspaceId]/home/hooks/use-lingxi-graph-chat.ts",
    'function artifactResourceId(taskId: string, artifact: string): string {\n  return `lingxi-artifact:${taskId}:${normalizeArtifactKind(artifact)}`\n}\n',
    '''function artifactResourceId(taskId: string, artifact: string): string {\n  return `lingxi-artifact:${taskId}:${normalizeArtifactKind(artifact)}`\n}\n\nconst RUNTIME_GRAPH_REFRESH_EVENTS = new Set([\n  'run.started',\n  'run.resumed',\n  'round.started',\n  'decision.recorded',\n  'node.started',\n  'node.completed',\n  'node.failed',\n  'node.held',\n  'node.revising',\n  'agent.started',\n  'agent.completed',\n  'agent.failed',\n])\n''',
)
replace(
    "web/app/workspace/[workspaceId]/home/hooks/use-lingxi-graph-chat.ts",
    '    let cancelled = false\n    setIsReconnecting(true)\n    setError(null)\n\n    const appendEvent = (event: AgentTaskEvent) => {',
    '''    let cancelled = false\n    let runtimeGraphRefreshTimer: ReturnType<typeof globalThis.setTimeout> | null = null\n    let runtimeGraphRefreshInFlight = false\n    setIsReconnecting(true)\n    setError(null)\n\n    const refreshRuntimeGraph = async () => {\n      if (cancelled || runtimeGraphRefreshInFlight) return\n      runtimeGraphRefreshInFlight = true\n      try {\n        const graph = await api.runtimeGraph(taskId)\n        if (!cancelled) setWorkflowState(graph.workflowState)\n      } catch {\n        // The graph endpoint can briefly lag identity persistence; the next\n        // lifecycle event/catch-up tick schedules another coalesced refresh.\n      } finally {\n        runtimeGraphRefreshInFlight = false\n      }\n    }\n\n    const scheduleRuntimeGraphRefresh = () => {\n      if (cancelled || runtimeGraphRefreshTimer !== null) return\n      runtimeGraphRefreshTimer = globalThis.setTimeout(() => {\n        runtimeGraphRefreshTimer = null\n        void refreshRuntimeGraph()\n      }, 150)\n    }\n\n    const appendEvent = (event: AgentTaskEvent) => {''',
)
replace(
    "web/app/workspace/[workspaceId]/home/hooks/use-lingxi-graph-chat.ts",
    '      if (eventWorkflowState) setWorkflowState(eventWorkflowState)\n      if (event.kind === \'artifact.ready\') {',
    '      if (eventWorkflowState) setWorkflowState(eventWorkflowState)\n      if (RUNTIME_GRAPH_REFRESH_EVENTS.has(event.kind)) scheduleRuntimeGraphRefresh()\n      if (event.kind === \'artifact.ready\') {',
)
replace(
    "web/app/workspace/[workspaceId]/home/hooks/use-lingxi-graph-chat.ts",
    '      if (envelope.type === \'resource\') {',
    '''      if (envelope.type === 'run' || envelope.type === 'span') {\n        scheduleRuntimeGraphRefresh()\n      }\n      if (envelope.type === 'resource') {''',
)
replace(
    "web/app/workspace/[workspaceId]/home/hooks/use-lingxi-graph-chat.ts",
    '      globalThis.clearInterval(v1CatchUpTimer)\n    }',
    '      globalThis.clearInterval(v1CatchUpTimer)\n      if (runtimeGraphRefreshTimer !== null) globalThis.clearTimeout(runtimeGraphRefreshTimer)\n    }',
)

# Strengthen existing behavior tests rather than relying only on source snapshots.
replace(
    "web/lib/lingxi/stream/turn-model.test.ts",
    "    expect(model.turns[0].assistantText).toBe('量子叠加是指一个系统可同时处于多个状态。')",
    "    expect(model.turns[0].assistantText).toBe('量子叠加是指一个系统可同时处于多个状态。')\n    expect(model.turns[0].blocks).toContainEqual(\n      expect.objectContaining({\n        type: 'text',\n        streamId: 's1',\n        content: '量子叠加是指一个系统可同时处于多个状态。',\n      })\n    )",
)
append(
    "web/lib/lingxi/live-stream-regression.test.ts",
    '''\n\ndescribe('Lingxi runtime graph live refresh regression', () => {\n  it('refreshes the graph from V0 lifecycle events and V1 replay/catch-up events', () => {\n    const source = readFileSync(hookPath, 'utf-8')\n    expect(source).toContain('RUNTIME_GRAPH_REFRESH_EVENTS.has(event.kind)')\n    expect(source).toContain("envelope.type === 'run' || envelope.type === 'span'")\n    expect(source).toContain('scheduleRuntimeGraphRefresh()')\n    expect(source).toContain('api.runtimeGraph(taskId)')\n  })\n})\n''',
)

# Backend regressions for the exact completion and planning failures in the trace.
(ROOT / "server/tests/test_durable_turn_regression.py").write_text('''from lingxilearn.runtime.completion import CompletionContext, evaluate\nfrom lingxilearn.runtime.contracts import CandidateAction, DoneCondition\nfrom lingxilearn.runtime.orchestrator import _default_done_condition\n\n\ndef test_provider_result_is_host_completion_fact_not_fake_evidence() -> None:\n    condition = DoneCondition(kind="provider_result")\n    assert evaluate(condition, CompletionContext(provider_result=True)).satisfied\n    assert not evaluate(condition, CompletionContext(provider_result=False)).satisfied\n\n\ndef test_structural_capabilities_default_to_provider_result() -> None:\n    candidate = CandidateAction(\n        candidate_id="candidate_prereq",\n        capability="graph.prerequisite",\n        skill_id="prerequisite-analyzer",\n        provider="prerequisite_analyzer",\n    )\n    condition = _default_done_condition(candidate)\n    assert condition.kind == "provider_result"\n    assert condition.signal == ""\n\n\ndef test_orchestrator_normalizes_legacy_provider_result_evidence_source() -> None:\n    source = (ROOT / "lingxilearn/runtime/orchestrator.py").read_text() if False else ""\n''')
# Remove the deliberately unused source placeholder and keep this file behavioral/clean.
replace(
    "server/tests/test_durable_turn_regression.py",
    '\n\ndef test_orchestrator_normalizes_legacy_provider_result_evidence_source() -> None:\n    source = (ROOT / "lingxilearn/runtime/orchestrator.py").read_text() if False else ""\n',
    '\n',
)

print("durable assistant/live graph patch applied")
