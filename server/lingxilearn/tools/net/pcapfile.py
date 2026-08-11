"""Classic libpcap container read/write (LINKTYPE_ETHERNET, microsecond).

Kept separate from the protocol codec so the file format and the wire format
can be tested independently — and so the round-trip test (synthesise → write →
read → decode → assert ground truth) has an obvious seam.
"""

from __future__ import annotations

import struct
from pathlib import Path

from .codec import Frame, decode

MAGIC_LE = 0xA1B2C3D4
MAGIC_BE = 0xD4C3B2A1
LINKTYPE_ETHERNET = 1
MAX_SNAPLEN = 262144


class PcapError(ValueError):
    """The file is not a capture we can read — surfaced to the learner as such."""


def write_pcap(path: str | Path, frames: list[tuple[float, bytes]]) -> Path:
    """Write frames as ``(unix_seconds, raw_bytes)`` pairs."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    out = bytearray()
    out += struct.pack("<IHHiIII", MAGIC_LE, 2, 4, 0, 0, MAX_SNAPLEN, LINKTYPE_ETHERNET)
    for ts, raw in frames:
        seconds = int(ts)
        micros = int(round((ts - seconds) * 1_000_000))
        if micros >= 1_000_000:  # rounding can carry
            seconds += 1
            micros -= 1_000_000
        out += struct.pack("<IIII", seconds, micros, len(raw), len(raw)) + raw
    target.write_bytes(bytes(out))
    return target


def read_pcap(path: str | Path, *, max_frames: int = 20000) -> list[Frame]:
    """Decode a capture into frames, refusing malformed input with a clear error."""
    target = Path(path)
    if not target.exists():
        raise PcapError(f"抓包文件不存在：{target.name}")
    blob = target.read_bytes()
    if len(blob) < 24:
        raise PcapError("文件太小，不是有效的 pcap 抓包。")

    magic = struct.unpack("<I", blob[:4])[0]
    if magic == MAGIC_LE:
        endian = "<"
    elif magic == MAGIC_BE:
        endian = ">"
    else:
        raise PcapError(
            "无法识别的文件头。LingxiLearn 目前支持经典 pcap（不支持 pcapng，"
            "可以先用 editcap 转换）。"
        )

    _vmaj, _vmin, _tz, _sig, _snap, linktype = struct.unpack(endian + "HHiIII", blob[4:24])
    if linktype != LINKTYPE_ETHERNET:
        raise PcapError(f"暂不支持的链路类型 {linktype}，本课程使用以太网抓包。")

    frames: list[Frame] = []
    offset, number = 24, 1
    while offset + 16 <= len(blob) and number <= max_frames:
        seconds, micros, captured, _original = struct.unpack(
            endian + "IIII", blob[offset : offset + 16]
        )
        offset += 16
        if captured > MAX_SNAPLEN or offset + captured > len(blob):
            raise PcapError(f"第 {number} 帧的长度字段越界，文件可能被截断。")
        raw = blob[offset : offset + captured]
        offset += captured
        frames.append(decode(number, seconds + micros / 1_000_000, raw))
        number += 1

    if not frames:
        raise PcapError("抓包里没有任何数据帧。")
    return frames
