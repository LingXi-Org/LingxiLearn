"""Synthesise the teaching captures.

Generated rather than recorded, deliberately:

* ground truth is known exactly, so grading is arithmetic rather than opinion;
* frame numbers are stable across regenerations, so hints can cite them;
* there is no real user traffic in the repository, so there is nothing to
  anonymise and nothing to leak.

The output is a real ``.pcap`` — open it in Wireshark and every field checks
out, including the checksums.  That is the point: the learner can audit us.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import codec
from .pcapfile import write_pcap

CLIENT_MAC = "aa:bb:cc:00:11:22"
ROUTER_MAC = "aa:bb:cc:00:33:44"

CLIENT_IP = "192.168.1.20"
RESOLVER_IP = "192.168.1.1"
SERVER_IP = "203.0.113.42"
HOSTNAME = "course.example.edu"

BASE_TS = 1_723_000_000.0
MSS = 1448


@dataclass
class Builder:
    frames: list[tuple[float, bytes]]

    def add(self, ts_ms: float, payload: bytes) -> int:
        self.frames.append((BASE_TS + ts_ms / 1000.0, payload))
        return len(self.frames)


def _c2s(payload: bytes) -> bytes:
    return codec.ethernet(ROUTER_MAC, CLIENT_MAC, payload)


def _s2c(payload: bytes) -> bytes:
    return codec.ethernet(CLIENT_MAC, ROUTER_MAC, payload)


def build_web_slow() -> tuple[list[tuple[float, bytes]], dict[str, Any]]:
    """「慢在哪一环」: a page load whose latency is spread across four causes.

    The numbers are chosen so no single bucket dominates by inspection — the
    learner has to actually measure, and the two classic confusions (calling
    server think time "网络慢", calling a retransmission stall "服务器慢") are
    both available as wrong answers.
    """
    b = Builder(frames=[])
    ground: dict[str, Any] = {}

    # --- DNS: a slow recursive resolution ------------------------------
    txid = 0x4E21
    q = codec.udp(CLIENT_IP, RESOLVER_IP, 51820, 53, codec.dns_query(txid, HOSTNAME))
    dns_q = b.add(0.0, _c2s(codec.ipv4(CLIENT_IP, RESOLVER_IP, q, proto=codec.PROTO_UDP, ident=1)))
    r = codec.udp(RESOLVER_IP, CLIENT_IP, 53, 51820, codec.dns_response(txid, HOSTNAME, [SERVER_IP]))
    dns_r = b.add(
        121.4, _s2c(codec.ipv4(RESOLVER_IP, CLIENT_IP, r, proto=codec.PROTO_UDP, ident=2))
    )
    ground["dns"] = {"frames": [dns_q, dns_r], "ms": 121.4}

    # --- TCP handshake: one clean RTT ----------------------------------
    cport, isn_c, isn_s = 51782, 1_000_000, 7_000_000
    syn = b.add(
        130.0,
        _c2s(
            codec.ipv4(
                CLIENT_IP,
                SERVER_IP,
                codec.tcp(
                    CLIENT_IP, SERVER_IP, cport, 80, seq=isn_c, flags=codec.TCP_SYN, window=64240
                ),
                proto=codec.PROTO_TCP,
                ident=3,
            )
        ),
    )
    synack = b.add(
        161.2,
        _s2c(
            codec.ipv4(
                SERVER_IP,
                CLIENT_IP,
                codec.tcp(
                    SERVER_IP,
                    CLIENT_IP,
                    80,
                    cport,
                    seq=isn_s,
                    ack=isn_c + 1,
                    flags=codec.TCP_SYN | codec.TCP_ACK,
                    window=65535,
                ),
                proto=codec.PROTO_TCP,
                ident=4,
            )
        ),
    )
    ack = b.add(
        161.9,
        _c2s(
            codec.ipv4(
                CLIENT_IP,
                SERVER_IP,
                codec.tcp(CLIENT_IP, SERVER_IP, cport, 80, seq=isn_c + 1, ack=isn_s + 1),
                proto=codec.PROTO_TCP,
                ident=5,
            )
        ),
    )
    ground["tcp_connect"] = {"frames": [syn, synack, ack], "ms": 31.9}

    # --- HTTP request, then a long server think time --------------------
    req = codec.http_request(HOSTNAME, "/lab/report")
    req_frame = b.add(
        163.0,
        _c2s(
            codec.ipv4(
                CLIENT_IP,
                SERVER_IP,
                codec.tcp(
                    CLIENT_IP,
                    SERVER_IP,
                    cport,
                    80,
                    seq=isn_c + 1,
                    ack=isn_s + 1,
                    flags=codec.TCP_ACK | codec.TCP_PSH,
                    payload=req,
                ),
                proto=codec.PROTO_TCP,
                ident=6,
            )
        ),
    )

    body = b"<html><body>" + b"LingxiLearn network lab payload. " * 180 + b"</body></html>"
    head = codec.http_response(body)
    chunks = [head[i : i + MSS] for i in range(0, len(head), MSS)]

    seq = isn_s + 1
    ack_c = isn_c + 1 + len(req)
    data_frames: list[int] = []
    t = 351.6  # first byte: 188.6 ms after the request left
    first_byte_ms = t

    lost_index = 2  # this segment is dropped on the wire, then retransmitted
    retransmit_of: int | None = None
    retransmit_seq = 0
    for index, chunk in enumerate(chunks):
        if index == lost_index:
            retransmit_seq = seq
            retransmit_of = None  # never appears the first time — it was lost
            seq += len(chunk)
            continue
        number = b.add(
            t,
            _s2c(
                codec.ipv4(
                    SERVER_IP,
                    CLIENT_IP,
                    codec.tcp(
                        SERVER_IP,
                        CLIENT_IP,
                        80,
                        cport,
                        seq=seq,
                        ack=ack_c,
                        flags=codec.TCP_ACK | codec.TCP_PSH,
                        payload=chunk,
                    ),
                    proto=codec.PROTO_TCP,
                    ident=10 + index,
                )
            ),
        )
        data_frames.append(number)
        seq += len(chunk)
        t += 6.4

    # Three duplicate ACKs: the receiver keeps asking for the missing bytes.
    dup_ack_frames = []
    for i in range(3):
        dup_ack_frames.append(
            b.add(
                t + 1.0 + i * 2.2,
                _c2s(
                    codec.ipv4(
                        CLIENT_IP,
                        SERVER_IP,
                        codec.tcp(
                            CLIENT_IP, SERVER_IP, cport, 80, seq=ack_c, ack=retransmit_seq
                        ),
                        proto=codec.PROTO_TCP,
                        ident=40 + i,
                    )
                ),
            )
        )

    # The stall, then the retransmission. This is the bucket students misread.
    stall_start = t + 1.0 + 2 * 2.2
    retransmit_ts = stall_start + 214.0
    lost_chunk = chunks[lost_index]
    original = b.add(
        retransmit_ts - 0.0001,
        _s2c(
            codec.ipv4(
                SERVER_IP,
                CLIENT_IP,
                codec.tcp(
                    SERVER_IP,
                    CLIENT_IP,
                    80,
                    cport,
                    seq=retransmit_seq,
                    ack=ack_c,
                    flags=codec.TCP_ACK | codec.TCP_PSH,
                    payload=lost_chunk,
                ),
                proto=codec.PROTO_TCP,
                ident=60,
            )
        ),
    )
    retransmit_of = original
    ground["retransmission"] = {
        "frames": [original],
        "stall_ms": round(retransmit_ts - (t - 6.4), 1),
    }

    fin = b.add(
        retransmit_ts + 8.0,
        _s2c(
            codec.ipv4(
                SERVER_IP,
                CLIENT_IP,
                codec.tcp(
                    SERVER_IP,
                    CLIENT_IP,
                    80,
                    cport,
                    seq=seq,
                    ack=ack_c,
                    flags=codec.TCP_ACK | codec.TCP_FIN,
                ),
                proto=codec.PROTO_TCP,
                ident=61,
            )
        ),
    )

    ground.update(
        {
            "hostname": HOSTNAME,
            "client": CLIENT_IP,
            "server": SERVER_IP,
            "resolver": RESOLVER_IP,
            "request_frame": req_frame,
            "first_byte_frame": data_frames[0] if data_frames else None,
            "first_byte_ms": first_byte_ms,
            "ttfb_ms": round(first_byte_ms - 163.0, 1),
            "data_frames": data_frames,
            "dup_ack_frames": dup_ack_frames,
            "retransmit_frame": retransmit_of,
            "fin_frame": fin,
            "frame_count": len(b.frames),
        }
    )
    return b.frames, ground


def build_dns_nxdomain() -> tuple[list[tuple[float, bytes]], dict[str, Any]]:
    """A failed lookup — used to teach that "打不开" and "很慢" are different faults."""
    b = Builder(frames=[])
    txid = 0x7A03
    name = "typo.exmaple.edu"
    q = codec.udp(CLIENT_IP, RESOLVER_IP, 52001, 53, codec.dns_query(txid, name))
    qf = b.add(0.0, _c2s(codec.ipv4(CLIENT_IP, RESOLVER_IP, q, proto=codec.PROTO_UDP, ident=1)))
    r = codec.udp(RESOLVER_IP, CLIENT_IP, 53, 52001, codec.dns_response(txid, name, [], rcode=3))
    rf = b.add(18.7, _s2c(codec.ipv4(RESOLVER_IP, CLIENT_IP, r, proto=codec.PROTO_UDP, ident=2)))
    return b.frames, {"query_frame": qf, "response_frame": rf, "rcode": 3, "name": name}


SCENARIOS = {
    "web-slow": build_web_slow,
    "dns-nxdomain": build_dns_nxdomain,
}


def generate(name: str, path: str | Path) -> dict[str, Any]:
    if name not in SCENARIOS:
        raise KeyError(f"unknown scenario: {name}")
    frames, ground = SCENARIOS[name]()
    written = write_pcap(path, frames)
    return {"scenario": name, "path": str(written), "frames": len(frames), "ground_truth": ground}
