"""FR-PLT-07, P112: spoofed X-Forwarded-For does not affect the verified IP
unless it came through a configured trusted proxy CIDR."""

from __future__ import annotations

from packages.platform.proxy import resolve_verified_peer_ip

TRUSTED = ("10.0.0.0/8",)


def test_untrusted_peer_spoofing_xff_is_ignored():
    ip = resolve_verified_peer_ip(
        peer_ip="203.0.113.5",
        forwarded_for="1.2.3.4",
        trusted_proxy_cidrs=TRUSTED,
    )
    assert ip == "203.0.113.5"


def test_trusted_proxy_xff_is_honored():
    ip = resolve_verified_peer_ip(
        peer_ip="10.0.0.1",
        forwarded_for="198.51.100.9",
        trusted_proxy_cidrs=TRUSTED,
    )
    assert ip == "198.51.100.9"


def test_trusted_proxy_takes_rightmost_hop_of_xff_chain():
    ip = resolve_verified_peer_ip(
        peer_ip="10.0.0.1",
        forwarded_for="198.51.100.9, 10.0.0.1",
        trusted_proxy_cidrs=TRUSTED,
    )
    assert ip == "10.0.0.1"


def test_trusted_proxy_with_no_xff_header_falls_back_to_peer_ip():
    ip = resolve_verified_peer_ip(peer_ip="10.0.0.1", forwarded_for=None, trusted_proxy_cidrs=TRUSTED)
    assert ip == "10.0.0.1"


def test_no_trusted_cidrs_configured_always_uses_raw_peer_ip():
    ip = resolve_verified_peer_ip(peer_ip="10.0.0.1", forwarded_for="9.9.9.9", trusted_proxy_cidrs=())
    assert ip == "10.0.0.1"


def test_malformed_xff_value_falls_back_to_peer_ip():
    ip = resolve_verified_peer_ip(
        peer_ip="10.0.0.1",
        forwarded_for="not-an-ip",
        trusted_proxy_cidrs=TRUSTED,
    )
    assert ip == "10.0.0.1"
