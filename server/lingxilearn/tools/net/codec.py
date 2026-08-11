"""Byte-level encoder/decoder for the protocol stack the course actually teaches.

Written against the RFCs rather than pulled from a library on purpose:

* the captures we emit are **real** ``.pcap`` files that open in Wireshark, so a
  student can check our teaching against the tool their course already uses;
* every field the tutor cites is one we decoded ourselves, so a frame number or
  a sequence number in a hint is computed, never recalled — which is exactly the
  thing a chat model cannot do with a binary artefact.

Scope is deliberately the undergraduate syllabus: Ethernet II, IPv4, TCP, UDP,
DNS and enough HTTP/1.1 to see a request and a response.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Any

ETH_TYPE_IPV4 = 0x0800
PROTO_TCP = 6
PROTO_UDP = 17

TCP_FIN, TCP_SYN, TCP_RST, TCP_PSH, TCP_ACK = 0x01, 0x02, 0x04, 0x08, 0x10


def checksum16(data: bytes) -> int:
    """The standard Internet checksum (RFC 1071)."""
    if len(data) % 2:
        data += b"\x00"
    total = 0
    for i in range(0, len(data), 2):
        total += (data[i] << 8) | data[i + 1]
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return (~total) & 0xFFFF


def mac(text: str) -> bytes:
    return bytes(int(part, 16) for part in text.split(":"))


def ip(text: str) -> bytes:
    return bytes(int(part) for part in text.split("."))


def ip_str(raw: bytes) -> str:
    return ".".join(str(b) for b in raw)


def mac_str(raw: bytes) -> str:
    return ":".join(f"{b:02x}" for b in raw)


# --------------------------------------------------------------------------
# Encoding
# --------------------------------------------------------------------------


def ethernet(dst: str, src: str, payload: bytes, ethertype: int = ETH_TYPE_IPV4) -> bytes:
    return mac(dst) + mac(src) + struct.pack("!H", ethertype) + payload


def ipv4(
    src: str,
    dst: str,
    payload: bytes,
    *,
    proto: int,
    ident: int = 0,
    ttl: int = 64,
    dont_fragment: bool = True,
) -> bytes:
    total_length = 20 + len(payload)
    flags_frag = 0x4000 if dont_fragment else 0
    header = struct.pack(
        "!BBHHHBBH4s4s",
        0x45,
        0x00,
        total_length,
        ident & 0xFFFF,
        flags_frag,
        ttl,
        proto,
        0,
        ip(src),
        ip(dst),
    )
    checksum = checksum16(header)
    header = header[:10] + struct.pack("!H", checksum) + header[12:]
    return header + payload


def _l4_checksum(src: str, dst: str, proto: int, segment: bytes) -> int:
    pseudo = ip(src) + ip(dst) + struct.pack("!BBH", 0, proto, len(segment))
    return checksum16(pseudo + segment)


def tcp(
    src_ip: str,
    dst_ip: str,
    src_port: int,
    dst_port: int,
    *,
    seq: int,
    ack: int = 0,
    flags: int = TCP_ACK,
    window: int = 64240,
    payload: bytes = b"",
    options: bytes = b"",
) -> bytes:
    if len(options) % 4:
        options += b"\x00" * (4 - len(options) % 4)
    offset_words = 5 + len(options) // 4
    header = struct.pack(
        "!HHIIBBHHH",
        src_port,
        dst_port,
        seq & 0xFFFFFFFF,
        ack & 0xFFFFFFFF,
        (offset_words << 4),
        flags,
        window,
        0,
        0,
    )
    segment = header + options + payload
    checksum = _l4_checksum(src_ip, dst_ip, PROTO_TCP, segment)
    segment = segment[:16] + struct.pack("!H", checksum) + segment[18:]
    return segment


def udp(src_ip: str, dst_ip: str, src_port: int, dst_port: int, payload: bytes) -> bytes:
    header = struct.pack("!HHHH", src_port, dst_port, 8 + len(payload), 0)
    datagram = header + payload
    checksum = _l4_checksum(src_ip, dst_ip, PROTO_UDP, datagram)
    return datagram[:6] + struct.pack("!H", checksum or 0xFFFF) + datagram[8:]


def dns_name(name: str) -> bytes:
    out = b""
    for label in name.strip(".").split("."):
        out += bytes([len(label)]) + label.encode("ascii")
    return out + b"\x00"


def dns_query(txid: int, name: str, qtype: int = 1) -> bytes:
    header = struct.pack("!HHHHHH", txid, 0x0100, 1, 0, 0, 0)
    return header + dns_name(name) + struct.pack("!HH", qtype, 1)


def dns_response(
    txid: int, name: str, addresses: list[str], *, ttl: int = 60, rcode: int = 0
) -> bytes:
    flags = 0x8180 | (rcode & 0x0F)
    header = struct.pack("!HHHHHH", txid, flags, 1, len(addresses), 0, 0)
    body = dns_name(name) + struct.pack("!HH", 1, 1)
    for address in addresses:
        body += b"\xc0\x0c" + struct.pack("!HHIH", 1, 1, ttl, 4) + ip(address)
    return header + body


def http_request(host: str, path: str = "/", *, method: str = "GET") -> bytes:
    lines = [
        f"{method} {path} HTTP/1.1",
        f"Host: {host}",
        "User-Agent: LingxiLearn/1.0",
        "Accept: text/html",
        "Connection: keep-alive",
        "",
        "",
    ]
    return "\r\n".join(lines).encode("ascii")


def http_response(body: bytes, *, status: str = "200 OK", ctype: str = "text/html") -> bytes:
    head = "\r\n".join(
        [
            f"HTTP/1.1 {status}",
            "Server: lingxilearn-demo",
            f"Content-Type: {ctype}",
            f"Content-Length: {len(body)}",
            "",
            "",
        ]
    ).encode("ascii")
    return head + body


# --------------------------------------------------------------------------
# Decoding
# --------------------------------------------------------------------------


@dataclass(slots=True)
class Frame:
    """One decoded frame. ``number`` is 1-based to match Wireshark."""

    number: int
    ts: float
    raw: bytes
    layers: dict[str, Any] = field(default_factory=dict)

    @property
    def protocol(self) -> str:
        for name in ("dns", "http", "tcp", "udp", "ipv4", "eth"):
            if name in self.layers:
                return name.upper()
        return "?"

    def summary(self) -> str:
        tcp_layer = self.layers.get("tcp")
        if "dns" in self.layers:
            d = self.layers["dns"]
            kind = "response" if d["is_response"] else "query"
            answers = ",".join(d.get("answers", []))
            return f"DNS {kind} {d.get('qname', '')}" + (f" → {answers}" if answers else "")
        if "http" in self.layers:
            h = self.layers["http"]
            return f"HTTP {h.get('start_line', '')}"
        if tcp_layer:
            return (
                f"TCP {tcp_layer['flag_names']} "
                f"seq={tcp_layer['seq_rel']} ack={tcp_layer['ack_rel']} "
                f"len={tcp_layer['payload_len']}"
            )
        return self.protocol

    def to_dict(self, *, with_bytes: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "number": self.number,
            "ts": round(self.ts, 6),
            "length": len(self.raw),
            "protocol": self.protocol,
            "summary": self.summary(),
            "layers": self.layers,
        }
        if with_bytes:
            data["hex"] = self.raw.hex()
        return data


def _decode_dns(payload: bytes) -> dict[str, Any] | None:
    if len(payload) < 12:
        return None
    txid, flags, qd, an, _ns, _ar = struct.unpack("!HHHHHH", payload[:12])
    offset = 12
    labels: list[str] = []
    try:
        while offset < len(payload):
            length = payload[offset]
            if length == 0:
                offset += 1
                break
            if length & 0xC0:  # compression pointer
                offset += 2
                break
            labels.append(payload[offset + 1 : offset + 1 + length].decode("ascii", "replace"))
            offset += 1 + length
        qname = ".".join(labels)
        qtype = qclass = 0
        if offset + 4 <= len(payload):
            qtype, qclass = struct.unpack("!HH", payload[offset : offset + 4])
            offset += 4
    except (IndexError, struct.error):
        return None

    answers: list[str] = []
    for _ in range(an):
        if offset + 12 > len(payload):
            break
        if payload[offset] & 0xC0:
            offset += 2
        else:
            while offset < len(payload) and payload[offset]:
                offset += 1 + payload[offset]
            offset += 1
        if offset + 10 > len(payload):
            break
        rtype, _rclass, _ttl, rdlen = struct.unpack("!HHIH", payload[offset : offset + 10])
        offset += 10
        rdata = payload[offset : offset + rdlen]
        offset += rdlen
        if rtype == 1 and len(rdata) == 4:
            answers.append(ip_str(rdata))

    return {
        "txid": txid,
        "flags": flags,
        "is_response": bool(flags & 0x8000),
        "rcode": flags & 0x0F,
        "qname": qname,
        "qtype": qtype,
        "qclass": qclass,
        "answer_count": an,
        "question_count": qd,
        "answers": answers,
    }


def _decode_http(payload: bytes) -> dict[str, Any] | None:
    if not payload:
        return None
    head = payload[:4]
    if not (head.startswith((b"GET", b"POST", b"HTTP", b"HEAD", b"PUT"))):
        return None
    try:
        text = payload.split(b"\r\n\r\n", 1)[0].decode("ascii", "replace")
    except Exception:  # noqa: BLE001
        return None
    lines = text.split("\r\n")
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            key, _, value = line.partition(":")
            headers[key.strip().lower()] = value.strip()
    return {
        "start_line": lines[0] if lines else "",
        "is_response": payload.startswith(b"HTTP"),
        "headers": headers,
    }


def _flag_names(flags: int) -> str:
    names = [
        ("FIN", TCP_FIN),
        ("SYN", TCP_SYN),
        ("RST", TCP_RST),
        ("PSH", TCP_PSH),
        ("ACK", TCP_ACK),
    ]
    active = [name for name, bit in names if flags & bit]
    return ",".join(active) if active else "-"


def decode(number: int, ts: float, raw: bytes) -> Frame:
    frame = Frame(number=number, ts=ts, raw=raw)
    if len(raw) < 14:
        return frame
    dst, src, ethertype = raw[0:6], raw[6:12], struct.unpack("!H", raw[12:14])[0]
    frame.layers["eth"] = {
        "dst": mac_str(dst),
        "src": mac_str(src),
        "ethertype": ethertype,
    }
    if ethertype != ETH_TYPE_IPV4 or len(raw) < 34:
        return frame

    ihl = (raw[14] & 0x0F) * 4
    total_length, ident, flags_frag, ttl, proto = struct.unpack("!HHHBB", raw[16:24])
    ip_header_end = 14 + ihl
    frame.layers["ipv4"] = {
        "src": ip_str(raw[26:30]),
        "dst": ip_str(raw[30:34]),
        "ttl": ttl,
        "proto": proto,
        "ident": ident,
        "total_length": total_length,
        "header_length": ihl,
        "dont_fragment": bool(flags_frag & 0x4000),
    }
    body = raw[ip_header_end : 14 + total_length] if total_length else raw[ip_header_end:]

    if proto == PROTO_TCP and len(body) >= 20:
        sport, dport, seq, ack, offset_byte, flags, window = struct.unpack("!HHIIBBH", body[:16])
        data_offset = (offset_byte >> 4) * 4
        payload = body[data_offset:]
        frame.layers["tcp"] = {
            "src_port": sport,
            "dst_port": dport,
            "seq": seq,
            "ack": ack,
            "seq_rel": 0,
            "ack_rel": 0,
            "flags": flags,
            "flag_names": _flag_names(flags),
            "window": window,
            "payload_len": len(payload),
            "header_length": data_offset,
        }
        http = _decode_http(payload)
        if http:
            frame.layers["http"] = http
    elif proto == PROTO_UDP and len(body) >= 8:
        sport, dport, length, _cs = struct.unpack("!HHHH", body[:8])
        payload = body[8:length] if length >= 8 else body[8:]
        frame.layers["udp"] = {
            "src_port": sport,
            "dst_port": dport,
            "length": length,
            "payload_len": len(payload),
        }
        if 53 in (sport, dport):
            dns = _decode_dns(payload)
            if dns:
                frame.layers["dns"] = dns
    return frame
