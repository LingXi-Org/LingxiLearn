"""Capture analysis: flows, ladder timeline, retransmissions, latency waterfall.

The waterfall is the pedagogical centre of the「慢在哪一环」mission.  It splits
the page-load wall clock into buckets that **partition** it — no overlap, no
double counting — because the learner is asked to allocate that same total, and
a rubric you cannot add up is a rubric you cannot grade.

    total = dns + tcp_connect + ttfb + transfer + retransmission + idle

``retransmission`` is carved out of the transfer window rather than laid on top
of it: it is the stall time while the sender waited for a timeout, which is
precisely the thing a student mis-attributes to "服务器慢".
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .codec import TCP_ACK, TCP_FIN, TCP_SYN, Frame


@dataclass(slots=True)
class Flow:
    key: str
    protocol: str
    client: str
    server: str
    client_port: int
    server_port: int
    frames: list[int] = field(default_factory=list)
    bytes_c2s: int = 0
    bytes_s2c: int = 0
    started: float = 0.0
    ended: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "protocol": self.protocol,
            "client": self.client,
            "server": self.server,
            "client_port": self.client_port,
            "server_port": self.server_port,
            "frames": list(self.frames),
            "bytes_c2s": self.bytes_c2s,
            "bytes_s2c": self.bytes_s2c,
            "started": round(self.started, 6),
            "ended": round(self.ended, 6),
            "duration_ms": round((self.ended - self.started) * 1000, 3),
        }


def _endpoint(frame: Frame) -> tuple[str, str, int, int, str] | None:
    ipv4 = frame.layers.get("ipv4")
    if not ipv4:
        return None
    layer = frame.layers.get("tcp") or frame.layers.get("udp")
    if not layer:
        return None
    proto = "tcp" if "tcp" in frame.layers else "udp"
    return (ipv4["src"], ipv4["dst"], layer["src_port"], layer["dst_port"], proto)


def build_flows(frames: list[Frame]) -> list[Flow]:
    """Group frames into bidirectional flows and fill in relative sequence numbers.

    Wireshark shows relative sequence numbers because absolute ISNs are noise;
    students compare ``seq``/``len`` against each other, so we normalise the
    same way and cite the same numbers they will see.
    """
    flows: dict[str, Flow] = {}
    isn: dict[tuple[str, int, str, int], int] = {}

    for frame in frames:
        parts = _endpoint(frame)
        if parts is None:
            continue
        src, dst, sport, dport, proto = parts
        forward = (src, sport, dst, dport)
        reverse = (dst, dport, src, sport)
        key_tuple = min(forward, reverse)
        key = f"{proto}:{key_tuple[0]}:{key_tuple[1]}-{key_tuple[2]}:{key_tuple[3]}"

        tcp = frame.layers.get("tcp")
        if tcp is not None:
            # Each side's ISN is learned from its own SYN, so both directions
            # get Wireshark-style relative numbers the learner can compare.
            if tcp["flags"] & TCP_SYN:
                isn[forward] = tcp["seq"]
            if forward in isn:
                tcp["seq_rel"] = (tcp["seq"] - isn[forward]) & 0xFFFFFFFF
            if reverse in isn and isn[reverse]:
                tcp["ack_rel"] = (tcp["ack"] - isn[reverse]) & 0xFFFFFFFF
            elif tcp["ack"]:
                tcp["ack_rel"] = tcp["ack"]

        if key not in flows:
            client, server = (src, dst)
            cport, sport_ = sport, dport
            if tcp is not None and not (tcp["flags"] & TCP_SYN and not tcp["flags"] & TCP_ACK):
                pass
            flows[key] = Flow(
                key=key,
                protocol=proto,
                client=client,
                server=server,
                client_port=cport,
                server_port=sport_,
                started=frame.ts,
            )
        flow = flows[key]
        flow.frames.append(frame.number)
        flow.ended = frame.ts
        payload = (frame.layers.get("tcp") or frame.layers.get("udp") or {}).get("payload_len", 0)
        if src == flow.client:
            flow.bytes_c2s += payload
        else:
            flow.bytes_s2c += payload

    # A SYN seen mid-capture may have flipped client/server; fix from the SYN.
    for frame in frames:
        tcp = frame.layers.get("tcp")
        ipv4 = frame.layers.get("ipv4")
        if not tcp or not ipv4:
            continue
        if tcp["flags"] & TCP_SYN and not tcp["flags"] & TCP_ACK:
            for flow in flows.values():
                if frame.number in flow.frames:
                    flow.client, flow.server = ipv4["src"], ipv4["dst"]
                    flow.client_port, flow.server_port = tcp["src_port"], tcp["dst_port"]
    return list(flows.values())


def detect_retransmissions(frames: list[Frame]) -> list[dict[str, Any]]:
    """Flag retransmitted segments and duplicate ACKs.

    Two rules, because a capture taken at the client never sees the segment
    that was lost — only the one that eventually fills the hole:

    ``retransmission``
        the exact ``(seq, len)`` was already transmitted on this flow.
    ``gap_fill``
        a data segment arrives whose ``seq`` is *behind* the highest sequence
        already seen in that direction, i.e. it plugs an earlier hole.  This is
        the shape a fast retransmit takes from the receiver's vantage point,
        and it is what the three duplicate ACKs were asking for.

    ``stall_ms`` measures how long that direction carried no new data before
    the hole was filled — the wall-clock the learner must *not* file under
    "服务器慢".
    """
    seen: dict[tuple[str, int, int], int] = {}
    last_data_ts: dict[str, float] = {}
    highest_seq: dict[str, int] = {}
    ack_runs: dict[tuple[str, int], int] = defaultdict(int)
    findings: list[dict[str, Any]] = []

    for frame in frames:
        tcp = frame.layers.get("tcp")
        ipv4 = frame.layers.get("ipv4")
        if not tcp or not ipv4:
            continue
        direction = f"{ipv4['src']}:{tcp['src_port']}>{ipv4['dst']}:{tcp['dst_port']}"
        payload_len = tcp["payload_len"]

        if payload_len > 0:
            signature = (direction, tcp["seq"], payload_len)
            previous_ts = last_data_ts.get(direction, frame.ts)
            top = highest_seq.get(direction)
            if signature in seen:
                findings.append(
                    {
                        "kind": "retransmission",
                        "frame": frame.number,
                        "original_frame": seen[signature],
                        "direction": direction,
                        "seq_rel": tcp["seq_rel"],
                        "length": payload_len,
                        "stall_ms": round((frame.ts - previous_ts) * 1000, 3),
                        "ts": round(frame.ts, 6),
                    }
                )
            elif top is not None and tcp["seq"] < top:
                findings.append(
                    {
                        "kind": "gap_fill",
                        "frame": frame.number,
                        "original_frame": None,
                        "direction": direction,
                        "seq_rel": tcp["seq_rel"],
                        "length": payload_len,
                        "stall_ms": round((frame.ts - previous_ts) * 1000, 3),
                        "ts": round(frame.ts, 6),
                    }
                )
            else:
                seen[signature] = frame.number
            highest_seq[direction] = max(top or 0, tcp["seq"] + payload_len)
            last_data_ts[direction] = frame.ts
        elif tcp["flags"] & TCP_ACK and not tcp["flags"] & (TCP_SYN | TCP_FIN):
            key = (direction, tcp["ack"])
            ack_runs[key] += 1
            if ack_runs[key] >= 2:  # a repeat of an ACK already sent
                findings.append(
                    {
                        "kind": "duplicate_ack",
                        "frame": frame.number,
                        "direction": direction,
                        "ack_rel": tcp["ack_rel"],
                        "count": ack_runs[key],
                        "triggers_fast_retransmit": ack_runs[key] >= 3,
                        "ts": round(frame.ts, 6),
                    }
                )
    return findings


def _primary_http_flow(frames: list[Frame], flows: list[Flow]) -> Flow | None:
    http_frames = {f.number for f in frames if "http" in f.layers}
    candidates = [f for f in flows if http_frames.intersection(f.frames)]
    if not candidates:
        candidates = [f for f in flows if f.protocol == "tcp"]
    return max(candidates, key=lambda f: f.bytes_s2c, default=None)


def waterfall(frames: list[Frame]) -> dict[str, Any]:
    """Split the page-load wall clock into non-overlapping, citable buckets."""
    flows = build_flows(frames)
    retrans = detect_retransmissions(frames)
    by_number = {f.number: f for f in frames}

    buckets = {"dns": 0.0, "tcp_connect": 0.0, "ttfb": 0.0, "transfer": 0.0, "retransmission": 0.0}
    bucket_frames: dict[str, list[int]] = {k: [] for k in buckets}
    roles: dict[int, str] = {}

    # --- DNS ------------------------------------------------------------
    dns_query = next(
        (f for f in frames if f.layers.get("dns", {}).get("is_response") is False), None
    )
    dns_reply = None
    if dns_query is not None:
        txid = dns_query.layers["dns"]["txid"]
        dns_reply = next(
            (
                f
                for f in frames
                if f.layers.get("dns", {}).get("is_response")
                and f.layers["dns"]["txid"] == txid
                and f.ts >= dns_query.ts
            ),
            None,
        )
        roles[dns_query.number] = "dns_query"
    if dns_query is not None and dns_reply is not None:
        buckets["dns"] = (dns_reply.ts - dns_query.ts) * 1000
        bucket_frames["dns"] = [dns_query.number, dns_reply.number]
        roles[dns_reply.number] = "dns_response"

    flow = _primary_http_flow(frames, flows)
    result: dict[str, Any] = {
        "flows": [f.to_dict() for f in flows],
        "anomalies": retrans,
    }
    if flow is None:
        result.update(
            {"total_ms": 0.0, "buckets": buckets, "bucket_frames": bucket_frames, "frame_roles": {}}
        )
        return result

    flow_frames = [by_number[n] for n in flow.frames if n in by_number]

    def first(pred) -> Frame | None:  # noqa: ANN001
        return next((f for f in flow_frames if pred(f)), None)

    syn = first(lambda f: (f.layers.get("tcp", {}).get("flags", 0) & TCP_SYN)
                and not (f.layers["tcp"]["flags"] & TCP_ACK))
    synack = first(lambda f: (f.layers.get("tcp", {}).get("flags", 0) & TCP_SYN)
                   and (f.layers["tcp"]["flags"] & TCP_ACK))
    handshake_ack = None
    if synack is not None:
        handshake_ack = first(
            lambda f: f.ts > synack.ts
            and f.layers.get("tcp", {}).get("payload_len", 0) == 0
            and (f.layers["tcp"]["flags"] & TCP_ACK)
            and not (f.layers["tcp"]["flags"] & TCP_SYN)
        )
    request = first(lambda f: f.layers.get("http", {}).get("is_response") is False)
    responses = [f for f in flow_frames if f.layers.get("tcp", {}).get("payload_len", 0) > 0
                 and f.layers.get("ipv4", {}).get("src") == flow.server]

    for frame in (syn, synack, handshake_ack):
        if frame is not None:
            roles[frame.number] = {
                syn.number if syn else -1: "tcp_syn",
                synack.number if synack else -2: "tcp_synack",
                handshake_ack.number if handshake_ack else -3: "tcp_ack",
            }.get(frame.number, "tcp_handshake")
    if request is not None:
        roles[request.number] = "http_request"
    for frame in responses:
        roles.setdefault(frame.number, "http_response_data")

    if syn is not None and handshake_ack is not None:
        buckets["tcp_connect"] = (handshake_ack.ts - syn.ts) * 1000
        bucket_frames["tcp_connect"] = [
            n for n in (syn.number, synack.number if synack else None, handshake_ack.number) if n
        ]

    if request is not None and responses:
        buckets["ttfb"] = (responses[0].ts - request.ts) * 1000
        bucket_frames["ttfb"] = [request.number, responses[0].number]
        roles[responses[0].number] = "http_first_byte"

    recovery = [r for r in retrans if r["kind"] in ("retransmission", "gap_fill")]
    retx_frames = {r["frame"] for r in recovery}
    penalty = sum(r["stall_ms"] for r in recovery)
    if responses:
        span = (responses[-1].ts - responses[0].ts) * 1000
        buckets["retransmission"] = round(penalty, 3)
        buckets["transfer"] = round(max(0.0, span - penalty), 3)
        bucket_frames["transfer"] = [
            f.number for f in responses if f.number not in retx_frames
        ]
        # The duplicate ACKs are evidence for this bucket too: they are the
        # receiver telling us a hole exists, which is what the stall is about.
        dup_ack_frames = {r["frame"] for r in retrans if r["kind"] == "duplicate_ack"}
        originals = {r["original_frame"] for r in recovery if r["original_frame"]}
        bucket_frames["retransmission"] = sorted(retx_frames | originals | dup_ack_frames)
    for number in retx_frames:
        roles[number] = "tcp_retransmission"
    for finding in retrans:
        if finding["kind"] == "duplicate_ack":
            roles[finding["frame"]] = "tcp_duplicate_ack"

    total = (frames[-1].ts - frames[0].ts) * 1000
    accounted = sum(buckets.values())
    result.update(
        {
            "total_ms": round(total, 3),
            "accounted_ms": round(accounted, 3),
            "idle_ms": round(max(0.0, total - accounted), 3),
            "buckets": {k: round(v, 3) for k, v in buckets.items()},
            "bucket_frames": bucket_frames,
            "frame_roles": {str(k): v for k, v in sorted(roles.items())},
            "primary_flow": flow.key,
        }
    )
    return result


def ladder(frames: list[Frame], *, limit: int = 400) -> dict[str, Any]:
    """Time-space diagram data: host lanes plus one arrow per frame."""
    hosts: list[str] = []
    for frame in frames:
        ipv4 = frame.layers.get("ipv4")
        if not ipv4:
            continue
        for host in (ipv4["src"], ipv4["dst"]):
            if host not in hosts:
                hosts.append(host)

    base = frames[0].ts if frames else 0.0
    arrows = []
    for frame in frames[:limit]:
        ipv4 = frame.layers.get("ipv4")
        if not ipv4:
            continue
        arrows.append(
            {
                "frame": frame.number,
                "t_ms": round((frame.ts - base) * 1000, 3),
                "src": ipv4["src"],
                "dst": ipv4["dst"],
                "protocol": frame.protocol,
                "label": frame.summary(),
                "bytes": len(frame.raw),
            }
        )
    return {
        "hosts": hosts,
        "arrows": arrows,
        "span_ms": round((frames[-1].ts - base) * 1000, 3) if frames else 0.0,
        "truncated": len(frames) > limit,
    }
