"""NFR-SEC-01, P301: every documented SSRF-relevant address class is
blocked, IPv4 and IPv6, including the classes ipaddress alone doesn't
reliably flag (CGNAT, NAT64) -- pure logic, no DB/network, Fast gate."""

from __future__ import annotations

import ipaddress

import pytest

from packages.platform.egress.validator import is_blocked_ip

BLOCKED = [
    "127.0.0.1",  # loopback
    "10.0.0.1",  # RFC 1918
    "172.16.0.1",  # RFC 1918
    "192.168.1.1",  # RFC 1918
    "169.254.169.254",  # link-local / cloud metadata
    "169.254.1.1",  # link-local
    "0.0.0.0",  # unspecified
    "100.64.0.1",  # CGNAT
    "224.0.0.1",  # multicast
    "255.255.255.255",  # broadcast/reserved
    "::1",  # IPv6 loopback
    "fe80::1",  # IPv6 link-local
    "fc00::1",  # IPv6 ULA (private)
    "ff00::1",  # IPv6 multicast
    "::ffff:127.0.0.1",  # IPv4-mapped loopback
    "::ffff:10.0.0.1",  # IPv4-mapped RFC 1918
    "::ffff:169.254.169.254",  # IPv4-mapped metadata
    "64:ff9b::a00:1",  # NAT64 well-known prefix embedding a private IPv4
]

ALLOWED = [
    "8.8.8.8",
    "1.1.1.1",
    "93.184.216.34",  # example.com-class public address
    "2606:4700:4700::1111",  # public IPv6 (Cloudflare DNS)
]


@pytest.mark.parametrize("addr", BLOCKED)
def test_blocked_addresses_are_rejected(addr):
    assert is_blocked_ip(ipaddress.ip_address(addr)) is True


@pytest.mark.parametrize("addr", ALLOWED)
def test_public_addresses_are_not_blocked(addr):
    assert is_blocked_ip(ipaddress.ip_address(addr)) is False
