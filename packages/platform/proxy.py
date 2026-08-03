"""Trusted reverse-proxy CIDR + verified peer IP (FR-PLT-07, P112).

`X-Forwarded-For` is attacker-controlled unless the request's immediate TCP
peer is a configured trusted proxy — a spoofed header from anywhere else
must never influence lockout/rate-limit decisions.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Sequence


def resolve_verified_peer_ip(
    peer_ip: str,
    forwarded_for: str | None,
    trusted_proxy_cidrs: Sequence[str],
) -> str:
    networks = [ipaddress.ip_network(cidr) for cidr in trusted_proxy_cidrs]
    peer_addr = ipaddress.ip_address(peer_ip)
    peer_is_trusted_proxy = any(peer_addr in network for network in networks)

    if not peer_is_trusted_proxy or not forwarded_for:
        return peer_ip

    # Right-most entry is the one appended by the nearest (trusted) hop.
    candidate = forwarded_for.split(",")[-1].strip()
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return peer_ip
    return candidate
