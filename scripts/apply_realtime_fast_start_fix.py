from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_goal_interpreter() -> None:
    path = Path("server/lingxilearn/runtime/goal_interpreter.py")
    replace_once(path, "import logging\n", "import logging\nimport re\n")
    marker = '''def build_goal(\n    parsed: Mapping[str, Any],\n'''
    text = path.read_text(encoding="utf-8")
    insertion = '''_EXPLICIT_LEARN_RE = re.compile(\n    r"^(?:我)?(?:想要?|希望|要|准备|打算)?(?P<depth>彻底|系统(?:地)?|深入|全面)?"\n    r"(?P<verb>掌握|学习|学会|理解|搞懂|弄懂)(?P<topic>[^？?]{1,80})[。！!]?$"\n)\n\n\ndef explicit_learning_goal(\n    utterance: str,\n    *,\n    profile_rows: Sequence[Mapping[str, Any]] = (),\n    current_goal: Goal | None = None,\n) -> Goal | None:\n    """Parse only an unambiguous, explicit *new* learning goal locally.\n\n    This is semantic parsing, not routing: the orchestrator still decides what\n    runs from state. Ambiguous questions, corrections, interruptions and all\n    existing-goal turns continue through the model interpreter.\n    """\n\n    if current_goal is not None:\n        return None\n    text = str(utterance or "").strip()\n    match = _EXPLICIT_LEARN_RE.fullmatch(text)\n    if match is None:\n        return None\n    topic = match.group("topic").strip(" \\t，,。.!！")\n    if not topic:\n        return None\n    depth = str(match.group("depth") or "")\n    verb = str(match.group("verb") or "学习")\n    constraints = [f"{depth}{verb}"] if depth else []\n    return build_goal(\n        {\n            "goal_type": "learn",\n            "topic": topic,\n            "knowledge_points": [],\n            "expected_outcome": "",\n            "constraints": constraints,\n            "urgency": 0.5,\n            "is_interruption": False,\n            "is_correction": False,\n        },\n        utterance=text,\n        profile_rows=profile_rows,\n        created_by="explicit_goal_parser",\n    )\n\n\n'''
    if text.count(marker) != 1:
        raise SystemExit("goal_interpreter build_goal marker mismatch")
    path.write_text(text.replace(marker, insertion + marker, 1), encoding="utf-8")
    replace_once(
        path,
        '''    if not text:\n        raise ValueError("goal_interpreter requires a non-empty utterance")\n    if model is None:\n        raise GoalInterpretationUnavailable("目标识别模型不可用")\n\n    payload = {\n''',
        '''    if not text:\n        raise ValueError("goal_interpreter requires a non-empty utterance")\n    fast_goal = explicit_learning_goal(\n        text, profile_rows=profile_rows, current_goal=current_goal\n    )\n    if fast_goal is not None:\n        return fast_goal\n    if model is None:\n        raise GoalInterpretationUnavailable("目标识别模型不可用")\n\n    payload = {\n''',
    )
    replace_once(
        path,
        '''    "build_goal",\n    "interpret",\n''',
        '''    "build_goal",\n    "explicit_learning_goal",\n    "interpret",\n''',
    )


def patch_orchestrator() -> None:
    path = Path("server/lingxilearn/runtime/orchestrator.py")
    replace_once(path, "        tasks.insert(\n            0,\n", "        tasks.append(\n")
    replace_once(
        path,
        '''        )\n    # A control-plane round may contain only hold decisions.  This is valid\n''',
        '''        )\n\n    # A parallel-safe, non-critical observation may inform later rounds, but\n    # it must not become a hard gate in front of learner-facing critical work.\n    # This keeps the model free to choose both tasks while preserving the\n    # latency semantics declared by candidate metadata.\n    task_by_id = {task.id: task for task in tasks}\n    tasks = [\n        task.model_copy(\n            update={\n                "depends_on": [\n                    dependency\n                    for dependency in task.depends_on\n                    if not (\n                        task.estimated_cost.critical_path\n                        and (dependency_task := task_by_id.get(dependency)) is not None\n                        and dependency_task.estimated_cost.parallel_safe\n                        and not dependency_task.estimated_cost.critical_path\n                    )\n                ]\n            }\n        )\n        for task in tasks\n    ]\n\n    # A control-plane round may contain only hold decisions.  This is valid\n''',
    )
    replace_once(
        path,
        '''    payload = {\n        "goal": goal.to_dict(),\n''',
        '''    # `MAX_MODEL_CANDIDATES` is a real latency boundary, not merely a\n    # documentation constant. Rank by host-side utility and expose only the\n    # most useful options to the control-plane model.\n    model_candidates = sorted(candidates, key=lambda item: item.utility, reverse=True)[\n        :MAX_MODEL_CANDIDATES\n    ]\n\n    payload = {\n        "goal": goal.to_dict(),\n''',
    )
    replace_once(
        path,
        '''            for item in candidates\n        ],\n    }\n''',
        '''            for item in model_candidates\n        ],\n    }\n''',
    )
    replace_once(
        path,
        '''    by_key = {(item.capability, item.knowledge_point_id): item for item in candidates}\n''',
        '''    by_key = {\n        (item.capability, item.knowledge_point_id): item for item in model_candidates\n    }\n''',
    )


def patch_agent_event_route() -> None:
    path = Path("server/lingxilearn/api/routes.py")
    replace_once(
        path,
        '''    protocol_version = 1 if request.query_params.get("protocol") == "v1" else 0\n\n    # History hydration uses one atomic JSON snapshot so the client can render\n    # the final graph state without replaying every old event as a new run.\n    if request.query_params.get("format") == "json":\n        events = await svc.repo.agent_events_after_for_learner(\n            task_id,\n            context.learner_id,\n            0,\n            protocol_version=protocol_version,\n        )\n        return Response(\n            content=json.dumps({"events": events}, ensure_ascii=False, separators=(",", ":")),\n            media_type="application/json",\n        )\n\n    header = request.headers.get("last-event-id") or request.query_params.get("last_event_id")\n    try:\n        cursor = int(header) if header else 0\n    except ValueError:\n        cursor = 0\n''',
        '''    protocol_version = 1 if request.query_params.get("protocol") == "v1" else 0\n    header = request.headers.get("last-event-id") or request.query_params.get("last_event_id")\n    try:\n        cursor = int(header) if header else 0\n    except ValueError:\n        cursor = 0\n\n    # JSON hydration doubles as an incremental gap-recovery endpoint. The\n    # cursor is the durable DB event sequence (the same namespace as SSE id),\n    # not the logical sequence inside a V1 envelope.\n    if request.query_params.get("format") == "json":\n        events = await svc.repo.agent_events_after_for_learner(\n            task_id,\n            context.learner_id,\n            cursor,\n            protocol_version=protocol_version,\n        )\n        return Response(\n            content=json.dumps({"events": events}, ensure_ascii=False, separators=(",", ":")),\n            media_type="application/json",\n            headers={"Cache-Control": "no-store"},\n        )\n''',
    )


def patch_frontend_api() -> None:
    path = Path("web/lib/lingxi/api.ts")
    replace_once(
        path,
        '''export function agentTaskV1Events(taskId: string): Promise<{ events: AgentTaskEvent[] }> {\n  return request<{ events: AgentTaskEvent[] }>(\n    `/agent-tasks/${taskId}/events?format=json&protocol=v1`\n  )\n}\n''',
        '''export function agentTaskV1Events(\n  taskId: string,\n  from = 0\n): Promise<{ events: AgentTaskEvent[] }> {\n  const cursor = from > 0 ? `&last_event_id=${from}` : ''\n  return request<{ events: AgentTaskEvent[] }>(\n    `/agent-tasks/${taskId}/events?format=json&protocol=v1${cursor}`\n  )\n}\n''',
    )


def patch_chat_hook() -> None:
    path = Path("web/app/workspace/[workspaceId]/home/hooks/use-lingxi-graph-chat.ts")
    replace_once(path, "  const [subscriptionEpoch, setSubscriptionEpoch] = useState(0)\n", "")
    replace_once(
        path,
        '''  const v1ModelRef = useRef<LingxiV1ThreadModel | null>(null)\n''',
        '''  const v1ModelRef = useRef<LingxiV1ThreadModel | null>(null)\n  // Durable event-row cursor used by SSE replay and JSON gap recovery. This is\n  // deliberately separate from the V1 envelope's logical `lastSeq`.\n  const v1CursorRef = useRef(0)\n''',
    )
    replace_once(
        path,
        '''    v1ModelRef.current = null\n    setLocalUsers([])\n''',
        '''    v1ModelRef.current = null\n    v1CursorRef.current = 0\n    setLocalUsers([])\n''',
    )
    replace_once(
        path,
        '''    let cancelled = false\n    setIsReconnecting(true)\n''',
        '''    let cancelled = false\n    let v1PollTimer: ReturnType<typeof setInterval> | null = null\n    let v1PollInFlight = false\n    setIsReconnecting(true)\n''',
    )
    replace_once(
        path,
        '''    const applyV1Event = (row: AgentTaskEvent) => {\n      if (cancelled) return\n      const envelope = decodeLingxiMothershipEvent(row.payload)\n      if (!envelope) return\n      // The V1 turn/run statuses are authoritative when the protocol is\n      // available; the V0 reducer keeps serving tasks without V1 history.\n      applyTurnState(reduceV1TurnState(turnStateRef.current, envelope))\n''',
        '''    const applyV1Event = (row: AgentTaskEvent) => {\n      if (cancelled || row.sequence <= v1CursorRef.current) return\n      const envelope = decodeLingxiMothershipEvent(row.payload)\n      if (!envelope) return\n      v1CursorRef.current = row.sequence\n      // The V1 turn/run statuses are authoritative when the protocol is\n      // available; the V0 reducer keeps serving tasks without V1 history.\n      const nextTurnState = reduceV1TurnState(turnStateRef.current, envelope)\n      applyTurnState(nextTurnState)\n      if (nextTurnState !== 'active') optimisticActiveRef.current = false\n''',
    )
    replace_once(
        path,
        '''          if (!cancelled && v1History.events.length > 0) {\n            const model = buildV1ThreadModel(\n''',
        '''          if (!cancelled && v1History.events.length > 0) {\n            v1CursorRef.current = Math.max(\n              v1CursorRef.current,\n              ...v1History.events.map((row) => row.sequence)\n            )\n            const model = buildV1ThreadModel(\n''',
    )
    replace_once(
        path,
        '''        if (v1ModelRef.current) {\n          unsubscribeV1Ref.current = subscribeAgentV1Events(taskId, applyV1Event, {\n            from: v1ModelRef.current.lastSeq,\n          })\n        } else {\n''',
        '''        if (v1ModelRef.current) {\n          unsubscribeV1Ref.current = subscribeAgentV1Events(taskId, applyV1Event, {\n            from: v1CursorRef.current,\n          })\n        } else {\n''',
    )
    replace_once(
        path,
        '''          unsubscribeV1Ref.current = subscribeAgentV1Events(taskId, (row) => {\n            if (!v1ModelRef.current) {\n              v1ModelRef.current = emptyV1ThreadModel(taskId)\n            }\n            applyV1Event(row)\n          })\n        }\n      } catch (cause) {\n''',
        '''          unsubscribeV1Ref.current = subscribeAgentV1Events(\n            taskId,\n            (row) => {\n              if (!v1ModelRef.current) {\n                v1ModelRef.current = emptyV1ThreadModel(taskId)\n              }\n              applyV1Event(row)\n            },\n            { from: v1CursorRef.current }\n          )\n        }\n\n        // SSE remains the primary low-latency transport. This short incremental\n        // poll is a gap-recovery safety net for proxies/browser paths that\n        // buffer a streaming response; it reads only rows after the durable DB\n        // cursor, so no page refresh is required to discover new V1 output.\n        const pollV1 = async () => {\n          if (\n            cancelled ||\n            locallyStopped ||\n            turnStateRef.current !== 'active' ||\n            v1PollInFlight\n          )\n            return\n          v1PollInFlight = true\n          try {\n            const incremental = await agentTaskV1Events(taskId, v1CursorRef.current)\n            for (const row of incremental.events.sort((left, right) => left.sequence - right.sequence)) {\n              applyV1Event(row)\n            }\n          } catch {\n            /* SSE may still be healthy; retry the recovery poll on the next tick. */\n          } finally {\n            v1PollInFlight = false\n          }\n        }\n        v1PollTimer = setInterval(() => void pollV1(), 750)\n        void pollV1()\n      } catch (cause) {\n''',
    )
    replace_once(
        path,
        '''      unsubscribeV1Ref.current?.()\n      unsubscribeV1Ref.current = null\n    }\n  }, [applyTurnState, locallyStopped, resolvedChatId, subscriptionEpoch])\n''',
        '''      unsubscribeV1Ref.current?.()\n      unsubscribeV1Ref.current = null\n      if (v1PollTimer) clearInterval(v1PollTimer)\n      v1PollTimer = null\n    }\n  }, [applyTurnState, locallyStopped, resolvedChatId])\n''',
    )
    replace_once(path, "      setSubscriptionEpoch((current) => current + 1)\n", "")


def add_regressions() -> None:
    path = Path("server/tests/test_realtime_fast_start_regression.py")
    path.write_text(
        '''from __future__ import annotations\n\nimport pytest\n\nfrom lingxilearn.runtime.goal_interpreter import interpret\n\n\n@pytest.mark.asyncio\nasync def test_explicit_new_learning_goal_skips_control_plane_model() -> None:\n    goal = await interpret(\n        utterance="我要彻底掌握拉普拉斯变换",\n        model=None,\n        profile_rows=(),\n        current_goal=None,\n    )\n    assert goal.goal_type == "learn"\n    assert goal.topic == "拉普拉斯变换"\n    assert goal.created_by == "explicit_goal_parser"\n    assert "彻底掌握" in goal.constraints\n\n\ndef test_fast_start_contracts_are_wired_to_durable_cursor_and_candidate_cap() -> None:\n    from pathlib import Path\n\n    root = Path(__file__).resolve().parents[1]\n    orchestrator = (root / "lingxilearn" / "runtime" / "orchestrator.py").read_text(encoding="utf-8")\n    routes = (root / "lingxilearn" / "api" / "routes.py").read_text(encoding="utf-8")\n    assert ":MAX_MODEL_CANDIDATES" in orchestrator.replace(" ", "").replace("\\n", "")\n    assert "cursor," in routes\n    assert 'headers={"Cache-Control": "no-store"}' in routes\n''',
        encoding="utf-8",
    )


if __name__ == "__main__":
    patch_goal_interpreter()
    patch_orchestrator()
    patch_agent_event_route()
    patch_frontend_api()
    patch_chat_hook()
    add_regressions()
