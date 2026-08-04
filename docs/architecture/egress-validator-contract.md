# Egress validator + trusted source registry — contract

**Status:** Designed (0.A/0.C). Not implemented — implementation is Phase 1 task 1.C (worker-connector), once the eTender connector needs to make its first real outbound call. This document fixes the contract and where it lives in the architecture, per `docs/reports/PLAN-MISSION-1.md` §2 (task 0.C): "реализация полностью — в Phase 1, здесь — контракт и место в архитектуре."
**Requirements:** NFR-SEC-01, NFR-SEC-02, NFR-SEC-03, INV-10, P006, `docs/architecture/threat-model.md` T1/T2/T3.
**Owner package:** `packages/platform` (cross-cutting; see its `README.md` — "egress validator / trusted source registry" is explicitly platform scope, not `packages/tender`'s).

## Why this exists

v1 was compromised via SSRF: a connector followed an RSS-feed redirect into an internal address. The lesson (master plan §17, v1 audit, OWASP SSRF Prevention cheat sheet, referenced in the threat model as "S12") is that **no single check is sufficient** — not a scheme check, not a hostname allow-list checked once, not a status-code check. The validator below is deliberately layered so that a bug in any one layer does not reopen the hole.

## 1. Trusted source registry

A source (host) must be explicitly registered before the worker is permitted to make any outbound call to it. Registration is not just "add a hostname to a list" — the process itself is a control (threat model T2): a new source is validated by an actual scanner run before being trusted, not by structural checks (scheme/status code) alone.

Conceptual shape (exact table lives in a Phase 1 migration, not created here — no domain migration is written ahead of the phase that needs it, per `AGENTS.md`):

| Field | Purpose |
|---|---|
| `host` | Exact hostname permitted (no wildcards — a new subdomain is a new registration) |
| `allowed_schemes` | e.g. `{https}` — a source is not implicitly permitted on `http` |
| `status` | `pending_scan` / `trusted` / `revoked` — never `trusted` on creation |
| `scanner_run_reference` | Link to the actual validation run that promoted this source to `trusted` (audit trail — *what* was checked, not just *that* someone clicked "trust") |
| `registered_by`, `registered_at` | Who/when — this is a security-relevant configuration change, subject to the same audit discipline as an RBAC change |
| `revoked_at`, `revoked_reason` | Revocation is append-only metadata on the same row, not a delete (same discipline as user `disable`, `packages/platform/rbac`) |

A request to a host not in this registry with `status = trusted` is rejected before any DNS resolution is attempted.

## 2. Validation algorithm (per outbound call, and per redirect hop)

The validator is not a one-time gate at the start of a request — it runs **before DNS resolution and again after every redirect**, because a redirect can point anywhere, including somewhere the original host never would have.

For a candidate URL:

1. **Scheme check.** Only schemes in the source's `allowed_schemes` are permitted (reject `file://`, `gopher://`, etc. outright — this is the class of bug a "URL parsing" library mistake reintroduces if the validator is bypassed).
2. **Registry check.** The hostname must match a `trusted` row in the registry (§1). No match → reject, regardless of how plausible the host looks.
3. **Resolve.** The validator performs its own DNS resolution — it does not trust a resolution the HTTP client might perform separately later.
4. **IP-range check.** Every resolved address (the validator checks **all** returned addresses, not just the first) is checked against the blocked ranges: loopback, private (RFC 1918/RFC 4193), link-local (including the `169.254.169.254`/`fd00:ec2::254`-class cloud metadata addresses), and any other non-routable/reserved range — for both IPv4 and IPv6. Any blocked address in the result set fails the whole check.
5. **Connect to the checked address, not the hostname.** The actual TCP connection is made to the specific IP address that was just validated in step 4 (e.g. pinning the resolved IP for the connection, or re-validating immediately before connect with no gap for a second resolution to occur) — **not** a fresh hostname lookup performed by the underlying HTTP client. This closes the DNS-rebinding TOCTOU gap flagged in the threat model review (T1): a low-TTL DNS answer that resolves to something safe at check-time and something private at connect-time must not be exploitable.
6. **On redirect: repeat from step 1** for the redirect target. A redirect is never followed on trust of the original URL's validation — each hop is a new candidate URL.

## 3. Interface (for Phase 1 implementation to satisfy — not code yet)

The eventual `packages/platform` module exposes (conceptually — types will be finalized in 1.C against whatever HTTP client is chosen):

- A `TrustedSourceRegistry` lookup: given a hostname, returns its registry row or "not found."
- An `EgressValidator` that wraps outbound calls: given a URL, either returns a validated, connect-ready target (resolved IP + original host for TLS SNI/Host header) or raises a rejection with a specific reason (`scheme_not_allowed` / `host_not_registered` / `address_blocked` / `redirect_target_rejected`) — the rejection reason is logged with the correlation id (`NFR-OBS-01`) so a blocked attempt is diagnosable, not a silent failure (`AGENTS.md` hard ban #3: no silent fallback).
- The connector (`packages/tender`, Phase 1) calls the validator for the initial request and for every redirect the underlying HTTP client would otherwise follow automatically — which means redirect-following must be manual/single-hop-at-a-time in the connector, not delegated to the HTTP client's built-in "follow redirects" behavior.

## 4. Defense in depth (threat model T3)

The validator above is an application-layer control. Per the threat model, it is not the only layer: a network-policy-level egress restriction (container/VPC network policy denying the worker process any route to RFC 1918 space except where explicitly required) is the independent second layer, so a bug in the validator alone does not reopen SSRF. The exact mechanism depends on `D-HOST` (owner decision, blocks only the production-deployment part, not this contract) — tracked in `docs/CONTEXT.md`, not decided here.

## 5. What is explicitly not decided here

- The concrete HTTP client library Phase 1's connector uses, and how it exposes single-hop redirect control — a 1.A/1.C implementation decision.
- The exact schema/migration for the trusted source registry table — written when 1.C needs it, against whatever `packages/tender` connector design 1.A produces.
- Network-policy mechanism for defense-in-depth (§4) — blocked on `D-HOST`.
