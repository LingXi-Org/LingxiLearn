"""Deterministic reliable-delivery simulator — the「你来当发送方」mission.

The learner *is* the sender.  At every decision point they choose what a real
sender chooses — send, wait, retransmit one segment, retransmit the window —
and the network answers back.  Nothing here can be answered from memory: the
right move depends on the state the simulator is in, and the simulator reacts.

Design notes that matter:

* **Pure functions over a serialisable state.**  ``step`` takes a state dict
  and returns a new one, so every position is checkpointable and replayable and
  the interactive endpoint needs no session affinity.
* **Server-authoritative grading.**  The UI drives ``step`` for responsiveness,
  but the score comes from ``replay`` re-running the learner's whole action log
  from the seed.  A client cannot award itself goodput.
* **Own PRNG.**  A tiny LCG rather than :mod:`random`, so a seed reproduces the
  same loss pattern on any Python version, forever.  Reproducibility is a
  teaching requirement here, not a nicety.
"""

from __future__ import annotations

from typing import Any

SEG_SIZE = 1024
DUP_ACK_THRESHOLD = 3
TIMEOUT_TICKS = 12
BASE_LATENCY = 3


class _Lcg:
    """Numerical Recipes LCG — small, stable, and good enough for loss patterns."""

    __slots__ = ("state",)

    def __init__(self, seed: int) -> None:
        self.state = (seed ^ 0x5DEECE66D) & 0xFFFFFFFF

    def next(self) -> int:
        self.state = (1664525 * self.state + 1013904223) & 0xFFFFFFFF
        return self.state

    def _bits(self) -> int:
        # An LCG's low-order bits have short periods; take the high half.
        return (self.next() >> 16) & 0xFFFF

    def chance(self, percent: int) -> bool:
        return (self._bits() % 100) < percent

    def between(self, low: int, high: int) -> int:
        return low + self._bits() % max(1, high - low + 1)


SCENARIOS: dict[str, dict[str, Any]] = {
    "single-loss": {
        "title": "一个洞",
        "segments": 8,
        "window": 4,
        "loss_percent": 0,
        "forced_drops": [(2, 0)],
        "jitter": 0,
        "brief": "窗口 4，共 8 段。第 3 段的第一次传输会丢。",
    },
    "lossy-link": {
        "title": "抖动链路",
        "segments": 12,
        "window": 4,
        "loss_percent": 18,
        "forced_drops": [],
        "jitter": 2,
        "brief": "窗口 4，共 12 段，链路有约 18% 丢包和往返抖动。",
    },
}


def _new_state(scenario: str, seed: int) -> dict[str, Any]:
    spec = SCENARIOS[scenario]
    return {
        "scenario": scenario,
        "seed": seed,
        "tick": 0,
        "seg_size": SEG_SIZE,
        "total_segments": spec["segments"],
        "window_size": spec["window"],
        "base": 0,
        "next_seq": 0,
        "attempts": [0] * spec["segments"],
        "inflight": [],
        "acked": [],
        "receiver_expected": 0,
        "receiver_buffer": [],
        "delivered": 0,
        "timer": {"running": False, "seq": None, "expires_at": None},
        "dup_ack_count": 0,
        "last_ack": -1,
        "timeout_pending": False,
        "events": [],
        "actions": [],
        "flags": [],
        "done": False,
        "brief": spec["brief"],
        "title": spec["title"],
    }


def init(scenario: str = "single-loss", seed: int = 7) -> dict[str, Any]:
    """Fresh simulator state for a scenario/seed pair."""
    if scenario not in SCENARIOS:
        raise KeyError(f"unknown scenario: {scenario}")
    return _new_state(scenario, seed)


def _should_drop(state: dict[str, Any], seq: int, attempt: int) -> bool:
    spec = SCENARIOS[state["scenario"]]
    if [seq, attempt] in [list(d) for d in spec["forced_drops"]]:
        return True
    if not spec["loss_percent"]:
        return False
    rng = _Lcg(state["seed"] * 7919 + seq * 131 + attempt * 17)
    return rng.chance(spec["loss_percent"])


def _latency(state: dict[str, Any], seq: int, attempt: int) -> int:
    spec = SCENARIOS[state["scenario"]]
    if not spec["jitter"]:
        return BASE_LATENCY
    rng = _Lcg(state["seed"] * 104729 + seq * 31 + attempt * 7)
    return BASE_LATENCY + rng.between(0, spec["jitter"])


def _emit(state: dict[str, Any], kind: str, **payload: Any) -> None:
    state["events"].append({"tick": state["tick"], "kind": kind, **payload})


def _transmit(state: dict[str, Any], seq: int, *, retransmit: bool) -> None:
    attempt = state["attempts"][seq]
    state["attempts"][seq] = attempt + 1
    dropped = _should_drop(state, seq, attempt)
    arrival = state["tick"] + _latency(state, seq, attempt)
    state["inflight"].append(
        {
            "seq": seq,
            "sent_at": state["tick"],
            "arrives_at": arrival,
            "dropped": dropped,
            "attempt": attempt,
            "kind": "data",
        }
    )
    _emit(
        state,
        "retransmit" if retransmit else "send",
        seq=seq,
        attempt=attempt,
        will_drop=dropped,
    )
    if not state["timer"]["running"]:
        state["timer"] = {
            "running": True,
            "seq": state["base"],
            "expires_at": state["tick"] + TIMEOUT_TICKS,
        }


def _deliver(state: dict[str, Any]) -> None:
    """Advance the wire by one tick: arrivals, receiver logic, ACKs back."""
    still: list[dict[str, Any]] = []
    for packet in state["inflight"]:
        if packet["arrives_at"] > state["tick"]:
            still.append(packet)
            continue
        if packet["dropped"]:
            _emit(state, "lost", seq=packet["seq"], kind_of="data")
            continue

        if packet["kind"] == "data":
            seq = packet["seq"]
            if seq == state["receiver_expected"]:
                state["receiver_expected"] += 1
                while state["receiver_expected"] in state["receiver_buffer"]:
                    state["receiver_buffer"].remove(state["receiver_expected"])
                    state["receiver_expected"] += 1
                state["delivered"] = state["receiver_expected"] * SEG_SIZE
                _emit(state, "deliver", seq=seq, expected_now=state["receiver_expected"])
            elif seq > state["receiver_expected"]:
                if seq not in state["receiver_buffer"]:
                    state["receiver_buffer"].append(seq)
                _emit(state, "buffer", seq=seq, expected=state["receiver_expected"])
            else:
                _emit(state, "duplicate_data", seq=seq)
            # The receiver always answers with a cumulative ACK.
            still.append(
                {
                    "seq": state["receiver_expected"],
                    "sent_at": state["tick"],
                    "arrives_at": state["tick"] + BASE_LATENCY,
                    "dropped": False,
                    "attempt": 0,
                    "kind": "ack",
                }
            )
        else:  # an ACK reaching the sender
            ack = packet["seq"]
            if ack > state["base"]:
                state["base"] = ack
                state["dup_ack_count"] = 0
                state["acked"] = list(range(ack))
                state["timer"] = (
                    {"running": True, "seq": ack, "expires_at": state["tick"] + TIMEOUT_TICKS}
                    if ack < state["next_seq"]
                    else {"running": False, "seq": None, "expires_at": None}
                )
                _emit(state, "ack", ack=ack, cumulative=True)
            elif ack == state["last_ack"]:
                state["dup_ack_count"] += 1
                _emit(state, "dup_ack", ack=ack, count=state["dup_ack_count"])
            state["last_ack"] = ack
    state["inflight"] = still


def step(state: dict[str, Any], action: dict[str, Any] | None = None) -> dict[str, Any]:
    """Apply one learner action and advance the simulation by one tick."""
    state = _clone(state)
    if state["done"]:
        return state

    action = action or {"op": "wait"}
    op = str(action.get("op", "wait"))
    state["actions"].append({"tick": state["tick"], **action})

    window_room = state["next_seq"] < state["base"] + state["window_size"]
    data_left = state["next_seq"] < state["total_segments"]

    if op == "send":
        if window_room and data_left:
            _transmit(state, state["next_seq"], retransmit=False)
            state["next_seq"] += 1
        else:
            reason = "window_full" if not window_room else "no_data_left"
            _emit(state, "rejected", op=op, reason=reason)
            state["flags"].append(f"invalid_send:{reason}")
    elif op == "retransmit":
        seq = int(action.get("seq", state["base"]))
        if seq < state["base"]:
            _emit(state, "rejected", op=op, reason="already_acked", seq=seq)
            state["flags"].append("retransmit_acked_segment")
        elif seq >= state["next_seq"]:
            _emit(state, "rejected", op=op, reason="never_sent", seq=seq)
            state["flags"].append("retransmit_unsent_segment")
        else:
            if seq != state["base"]:
                state["flags"].append("retransmit_non_base")
            else:
                # Retransmitting the base is entering recovery: a real sender
                # fires fast retransmit once, not once per duplicate ACK.
                if state["dup_ack_count"] >= DUP_ACK_THRESHOLD:
                    state["flags"].append("fast_retransmit_taken")
                state["dup_ack_count"] = 0
                state["timeout_pending"] = False
            _transmit(state, seq, retransmit=True)
    elif op == "retransmit_all":
        outstanding = list(range(state["base"], state["next_seq"]))
        if len(outstanding) > 1:
            state["flags"].append("retransmit_whole_window")
        for seq in outstanding:
            _transmit(state, seq, retransmit=True)
    elif op == "wait":
        if window_room and data_left and not state["inflight"] and not state["timer"]["running"]:
            state["flags"].append("idle_with_room")
        _emit(state, "wait")
    else:
        _emit(state, "rejected", op=op, reason="unknown_op")

    # Note that recovery was available, so we can tell later whether the
    # learner acted on it. The "taken" flag is set in the retransmit branch.
    if state["dup_ack_count"] >= DUP_ACK_THRESHOLD:
        state["flags"].append("fast_retransmit_window_open")

    timer = state["timer"]
    if timer["running"] and timer["expires_at"] is not None and state["tick"] >= timer["expires_at"]:
        _emit(state, "timeout", seq=timer["seq"])
        state["flags"].append("timeout_fired")
        state["timeout_pending"] = True
        state["timer"] = {
            "running": True,
            "seq": state["base"],
            "expires_at": state["tick"] + TIMEOUT_TICKS,
        }

    state["tick"] += 1
    _deliver(state)

    if state["receiver_expected"] >= state["total_segments"]:
        state["done"] = True
        _emit(state, "complete", ticks=state["tick"])
    elif state["tick"] > 400:  # a stalled learner should not hang the server
        state["done"] = True
        state["flags"].append("gave_up")
        _emit(state, "aborted", reason="tick_limit")
    return state


def _clone(state: dict[str, Any]) -> dict[str, Any]:
    out = dict(state)
    for key in ("attempts", "inflight", "acked", "receiver_buffer", "events", "actions", "flags"):
        out[key] = [dict(v) if isinstance(v, dict) else v for v in state[key]]
    out["timer"] = dict(state["timer"])
    return out


def replay(scenario: str, seed: int, actions: list[dict[str, Any]]) -> dict[str, Any]:
    """Re-run a learner's whole action log from the seed. This is the grader's truth."""
    state = init(scenario, seed)
    for action in actions[:400]:
        if state["done"]:
            break
        state = step(state, action)
    return state


def oracle(scenario: str, seed: int) -> dict[str, Any]:
    """A correct sender: keep the window full, fast-retransmit on 3 dup ACKs."""
    state = init(scenario, seed)
    guard = 0
    while not state["done"] and guard < 400:
        guard += 1
        if state["dup_ack_count"] >= DUP_ACK_THRESHOLD or state.get("timeout_pending"):
            action = {"op": "retransmit", "seq": state["base"]}
        elif (
            state["next_seq"] < state["base"] + state["window_size"]
            and state["next_seq"] < state["total_segments"]
        ):
            action = {"op": "send"}
        else:
            action = {"op": "wait"}
        state = step(state, action)
    return {"ticks": state["tick"], "done": state["done"], "actions": state["actions"]}


def score(scenario: str, seed: int, actions: list[dict[str, Any]]) -> dict[str, Any]:
    """Grade a run: correctness first, then efficiency against the oracle.

    Misconceptions come from the *pattern of decisions*, which is why this task
    resists memorisation — there is no answer to recall, only a policy that
    either survives the network or doesn't.
    """
    final = replay(scenario, seed, actions)
    baseline = oracle(scenario, seed)

    intact = (
        final["receiver_expected"] >= final["total_segments"]
        and not final["receiver_buffer"]
    )
    ticks = max(1, final["tick"])
    efficiency = min(1.0, baseline["ticks"] / ticks) if final["done"] and intact else 0.0

    flags = final["flags"]
    misconceptions: list[str] = []

    def flag(name: str) -> int:
        return flags.count(name)

    if flag("fast_retransmit_window_open") and not flag("fast_retransmit_taken"):
        misconceptions.append("no_fast_retransmit")
    if flag("retransmit_whole_window"):
        misconceptions.append("gbn_vs_sr_confusion")
    if flag("retransmit_acked_segment"):
        misconceptions.append("cumulative_ack_misread")
    if flag("retransmit_non_base"):
        misconceptions.append("timer_per_packet_not_per_base")
    if flag("timeout_fired") >= 3 and not flag("fast_retransmit_taken"):
        misconceptions.append("ignores_timeout")
    if flag("idle_with_room") >= 3:
        misconceptions.append("window_never_fills")
    if flag("invalid_send:window_full") >= 2:
        misconceptions.append("window_limit_ignored")

    return {
        "delivered_intact": bool(intact),
        "efficiency": round(efficiency, 4),
        "misconceptions": misconceptions,
        "stats": {
            "ticks": final["tick"],
            "oracle_ticks": baseline["ticks"],
            "delivered_segments": final["receiver_expected"],
            "total_segments": final["total_segments"],
            "transmissions": sum(final["attempts"]),
            "retransmissions": sum(max(0, a - 1) for a in final["attempts"]),
            "flags": sorted(set(flags)),
        },
        "final_state": final,
    }
