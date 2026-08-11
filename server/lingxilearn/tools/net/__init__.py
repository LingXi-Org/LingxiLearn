"""Computer Networks toolbox — registers the ``net.*`` capabilities.

Everything here is a real computation over a real artefact.  No tool asks a
model what it thinks happened; the tutor's claims are downstream of these
return values, which is what makes a cited frame number checkable.
"""

from __future__ import annotations

import ipaddress
from typing import Any

from ..registry import ToolError, registry
from . import analysis, sim
from .pcapfile import PcapError, read_pcap

# --------------------------------------------------------------------------
# Capture analysis
# --------------------------------------------------------------------------


def _load(path: str):  # noqa: ANN202
    try:
        return read_pcap(path)
    except PcapError as exc:
        raise ToolError(str(exc), code="bad_capture") from exc


@registry.tool("net.pcap.summary")
def pcap_summary(path: str) -> dict:
    """Overview of a capture: frame count, time span, protocols and endpoints."""
    frames = _load(path)
    protocols: dict[str, int] = {}
    for frame in frames:
        protocols[frame.protocol] = protocols.get(frame.protocol, 0) + 1
    return {
        "frames": len(frames),
        "span_ms": round((frames[-1].ts - frames[0].ts) * 1000, 3),
        "protocols": protocols,
        "first_ts": frames[0].ts,
        "bytes": sum(len(f.raw) for f in frames),
    }


@registry.tool("net.pcap.frames")
def pcap_frames(path: str, limit: int = 200, offset: int = 0) -> list[dict]:
    """Decoded frame list with per-frame protocol summaries."""
    frames = _load(path)
    return [f.to_dict() for f in frames[offset : offset + limit]]


@registry.tool("net.pcap.frame")
def pcap_frame(path: str, number: int) -> dict:
    """One frame in full detail, including the decoded field tree and raw bytes."""
    frames = _load(path)
    match = next((f for f in frames if f.number == number), None)
    if match is None:
        raise ToolError(f"抓包中没有第 {number} 帧", code="no_such_frame")
    return match.to_dict(with_bytes=True)


@registry.tool("net.pcap.flows")
def pcap_flows(path: str) -> list[dict]:
    """Bidirectional flows with byte counts and durations."""
    return [f.to_dict() for f in analysis.build_flows(_load(path))]


@registry.tool("net.pcap.ladder")
def pcap_ladder(path: str, limit: int = 400) -> dict:
    """Time-space (ladder) diagram data: host lanes and one arrow per frame."""
    return analysis.ladder(_load(path), limit=limit)


@registry.tool("net.pcap.anomalies")
def pcap_anomalies(path: str) -> list[dict]:
    """Retransmissions, gap fills and duplicate ACKs, with the stall each caused."""
    return analysis.detect_retransmissions(_load(path))


@registry.tool("net.pcap.waterfall")
def pcap_waterfall(path: str) -> dict:
    """Latency budget that partitions page-load wall clock into citable buckets."""
    return analysis.waterfall(_load(path))


# --------------------------------------------------------------------------
# Reliable-delivery simulator
# --------------------------------------------------------------------------


@registry.tool("net.sim.init")
def sim_init(scenario: str = "single-loss", seed: int = 7) -> dict:
    """Fresh sender-side simulation state for a scenario and seed."""
    try:
        return sim.init(scenario, seed)
    except KeyError as exc:
        raise ToolError(f"未知的仿真场景：{scenario}", code="unknown_scenario") from exc


@registry.tool("net.sim.step")
def sim_step(state: dict, action: dict) -> dict:
    """Apply one sender decision and advance the simulation by a tick."""
    return sim.step(state, action)


@registry.tool("net.sim.oracle")
def sim_oracle(scenario: str = "single-loss", seed: int = 7) -> dict:
    """Run a correct sender to establish the efficiency baseline."""
    return sim.oracle(scenario, seed)


@registry.tool("net.sim.score")
def sim_score(scenario: str, seed: int, actions: list) -> dict:
    """Replay a learner's decisions from the seed and grade the outcome."""
    return sim.score(scenario, seed, list(actions or []))


@registry.tool("net.sim.scenarios")
def sim_scenarios() -> list[dict]:
    """List the available simulation scenarios."""
    return [
        {"id": key, "title": spec["title"], "brief": spec["brief"], **{
            k: spec[k] for k in ("segments", "window", "loss_percent")
        }}
        for key, spec in sim.SCENARIOS.items()
    ]


# --------------------------------------------------------------------------
# Addressing — registered for reuse, not on either mission's main path yet
# --------------------------------------------------------------------------


@registry.tool("net.ipv4.subnet")
def ipv4_subnet(cidr: str) -> dict:
    """Network, broadcast, host range and usable count for an IPv4 CIDR block."""
    try:
        net = ipaddress.IPv4Network(cidr, strict=False)
    except ValueError as exc:
        raise ToolError(f"无效的 CIDR：{cidr}", code="bad_cidr") from exc
    hosts = list(net.hosts())
    return {
        "cidr": str(net),
        "network": str(net.network_address),
        "broadcast": str(net.broadcast_address),
        "netmask": str(net.netmask),
        "prefix_length": net.prefixlen,
        "total_addresses": net.num_addresses,
        "usable_hosts": len(hosts),
        "first_host": str(hosts[0]) if hosts else None,
        "last_host": str(hosts[-1]) if hosts else None,
    }


@registry.tool("net.ipv4.lpm")
def ipv4_lpm(routes: list, destination: str) -> dict:
    """Longest-prefix match: which routing-table entry wins, and why."""
    try:
        target = ipaddress.IPv4Address(destination)
    except ValueError as exc:
        raise ToolError(f"无效的目的地址：{destination}", code="bad_address") from exc

    considered: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None
    for entry in routes or []:
        prefix = entry.get("prefix") if isinstance(entry, dict) else str(entry)
        try:
            net = ipaddress.IPv4Network(str(prefix), strict=False)
        except ValueError:
            continue
        matched = target in net
        considered.append(
            {"prefix": str(net), "matches": matched, "prefix_length": net.prefixlen,
             "next_hop": (entry.get("next_hop") if isinstance(entry, dict) else None)}
        )
        if matched and (best is None or net.prefixlen > best["prefix_length"]):
            best = considered[-1]
    return {"destination": destination, "considered": considered, "selected": best}


__all__ = ["analysis", "sim"]
