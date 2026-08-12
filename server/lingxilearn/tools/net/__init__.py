"""Computer Networks toolbox — registers the ``net.*`` capabilities.

Everything here is a real computation over a real artefact.  No tool asks a
model what it thinks happened; the tutor's claims are downstream of these
return values, which is what makes a cited frame number checkable.
"""

from __future__ import annotations

import ipaddress
from typing import Any

from ..registry import ToolError, registry

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
