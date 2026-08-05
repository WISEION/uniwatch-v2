"""Trusted reverse-proxy CIDR + verified peer IP (FR-PLT-07, P112).

`X-Forwarded-For` is attacker-controlled unless the request's immediate TCP
peer is a configured trusted proxy — a spoofed header from anywhere else
must never influence lockout/rate-limit decisions.
"""

from __future__ import annotations

import ipaddress
import logging
from collections.abc import Sequence

logger = logging.getLogger("uniwatch.platform.proxy")


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
        # Falling back to the TCP peer is the safe answer, but a *trusted*
        # proxy emitting an unparseable X-Forwarded-For is a real
        # misconfiguration (or an injection attempt through it) — silently
        # falling back would hide it.
        logger.warning(
            "trusted proxy %s sent an unparseable X-Forwarded-For entry %r — using the peer address instead",
            peer_ip,
            candidate,
        )
        return peer_ip
    return candidate
