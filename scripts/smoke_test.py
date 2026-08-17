"""Real-HTTP smoke test by role (Phase 6, task 6.B, task 3 -- Gate 5, master
plan Section 22 Gate 5's "critical route smoke by role" line).

Every existing test in this repo (tests/integration/test_auth_api.py,
tests/integration/test_admin_users_api.py, ...) drives the FastAPI app
in-process via httpx.ASGITransport. Gate 5 is a post-*deploy* verification
step, not a test: it needs to prove a genuinely running, already-deployed
server actually works end to end over real TCP/HTTP -- not just that the
code is correct in-process. This script is that proof: it connects with a
real httpx.Client, no ASGITransport anywhere.

For a small, representative set of roles this repo already has real routes
for, it logs in over real HTTP, hits one route that role's permissions
should allow (expect 200), one route they should NOT (expect 403 --
proving deny-by-default RBAC, AGENTS.md hard ban #7, is live-correct and
not just correct in the test suite), then logs out and re-hits the allowed
route (expect 401 -- proving logout actually revokes the session on a live
deployment, not just in a test fixture).

Credentials: a fresh deployment's database has no users at all, and even an
operator's existing real accounts are unlikely to already carry the exact
one-permission-each split this script needs to prove both halves of
deny-by-default RBAC. So rather than requiring the operator to hand-supply
matching accounts, this script logs in as the two throw-away accounts
`scripts/seed_smoke_test_users.py` creates (`smoke_test_admin_reader`,
`smoke_test_algorithm_reader`) -- run that script once against the target
deployment first. See its docstring for the full rationale. The
--*-username/--*-password flags below let you point at different accounts
seeded under the same two permissions, if you'd rather not use the
throw-away ones.

Usage:
    python scripts/seed_smoke_test_users.py       # once, against the target deployment
    python scripts/smoke_test.py --base-url http://localhost:8001

Exit code is non-zero if any check failed -- this script's exit code and
printed summary *are* Gate 5's smoke-test evidence, not decoration.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, replace

import httpx

DEFAULT_BASE_URL = "http://localhost:8001"  # docker-compose.local.yml's api_tender port


@dataclass(frozen=True)
class RoleCheck:
    label: str
    username: str
    password: str
    allowed_method: str
    allowed_path: str
    denied_method: str
    denied_path: str


# Matches scripts/seed_smoke_test_users.py::SMOKE_TEST_USERS exactly. Each
# role is deliberately single-permission, so "allowed" and "denied" prove
# deny-by-default RBAC rather than merely exercising two working routes.
DEFAULT_ROLE_CHECKS: tuple[RoleCheck, ...] = (
    RoleCheck(
        label="admin-reader (admin.users.read)",
        username="smoke_test_admin_reader",
        password="smoke-test-only-admin-reader-9f3a",
        allowed_method="GET",
        allowed_path="/admin/users",
        denied_method="GET",
        # algorithm.policy.read-gated; the graph need not exist -- the
        # permission dependency raises 403 before any graph lookup runs.
        denied_path="/policy-graphs/999999999/versions",
    ),
    RoleCheck(
        label="algorithm-reader (algorithm.policy.read)",
        username="smoke_test_algorithm_reader",
        password="smoke-test-only-algorithm-reader-7c2e",
        allowed_method="GET",
        # admin.users.read-gated on the other side; a non-existent graph_id
        # here still returns 200 with an empty version list (no FK
        # existence check in policy_store.list_versions_by_graph), so this
        # check exercises the permission gate without needing seeded graph
        # data.
        allowed_path="/policy-graphs/999999999/versions",
        denied_method="GET",
        denied_path="/admin/users",
    ),
)


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def _record(results: list[CheckResult], name: str, passed: bool, detail: str) -> None:
    results.append(CheckResult(name=name, passed=passed, detail=detail))


def check_health_ready(base_url: str, results: list[CheckResult]) -> None:
    """No auth needed. Reads schema_version/expected_schema_version out of
    the response body itself -- never hardcodes a version number, since
    that would silently drift from packages/platform/settings.py's own
    EXPECTED_SCHEMA_VERSION-driven value."""
    name = "health: GET /health/ready"
    try:
        response = httpx.get(f"{base_url}/health/ready", timeout=10.0)
    except httpx.HTTPError as exc:
        _record(results, name, False, f"request failed: {exc}")
        return

    if response.status_code != 200:
        _record(results, name, False, f"expected 200, got {response.status_code}: {response.text}")
        return

    body = response.json()
    schema_version = body.get("schema_version")
    expected_schema_version = body.get("expected_schema_version")
    if schema_version != expected_schema_version:
        _record(
            results,
            name,
            False,
            f"schema_version ({schema_version!r}) != expected_schema_version ({expected_schema_version!r})",
        )
        return
    _record(results, name, True, f"schema_version={schema_version}")


def check_role(base_url: str, check: RoleCheck, results: list[CheckResult]) -> None:
    """Login -> allowed route (200) -> denied route (403) -> logout (204)
    -> allowed route again (401). One fresh httpx.Client per role so
    cookies from one identity never leak into another's checks."""
    prefix = f"role[{check.label}]"
    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        try:
            login = client.post("/auth/login", json={"username": check.username, "password": check.password})
        except httpx.HTTPError as exc:
            _record(results, f"{prefix}: login", False, f"request failed: {exc}")
            return
        if login.status_code != 200:
            _record(results, f"{prefix}: login", False, f"expected 200, got {login.status_code}: {login.text}")
            return
        _record(results, f"{prefix}: login", True, f"logged in as {check.username}")

        try:
            allowed = client.request(check.allowed_method, check.allowed_path)
        except httpx.HTTPError as exc:
            _record(results, f"{prefix}: allowed route", False, f"request failed: {exc}")
        else:
            passed = allowed.status_code == 200
            _record(
                results,
                f"{prefix}: allowed route ({check.allowed_method} {check.allowed_path})",
                passed,
                "200 as expected" if passed else f"expected 200, got {allowed.status_code}: {allowed.text}",
            )

        try:
            denied = client.request(check.denied_method, check.denied_path)
        except httpx.HTTPError as exc:
            _record(results, f"{prefix}: denied route", False, f"request failed: {exc}")
        else:
            passed = denied.status_code == 403
            _record(
                results,
                f"{prefix}: denied route ({check.denied_method} {check.denied_path})",
                passed,
                "403 as expected (deny-by-default RBAC)" if passed else f"expected 403, got {denied.status_code}: {denied.text}",
            )

        try:
            logout = client.post("/auth/logout")
        except httpx.HTTPError as exc:
            _record(results, f"{prefix}: logout", False, f"request failed: {exc}")
            return
        passed = logout.status_code == 204
        _record(
            results,
            f"{prefix}: logout",
            passed,
            "204 as expected" if passed else f"expected 204, got {logout.status_code}: {logout.text}",
        )

        try:
            after_logout = client.request(check.allowed_method, check.allowed_path)
        except httpx.HTTPError as exc:
            _record(results, f"{prefix}: allowed route after logout", False, f"request failed: {exc}")
        else:
            passed = after_logout.status_code == 401
            _record(
                results,
                f"{prefix}: allowed route after logout ({check.allowed_method} {check.allowed_path})",
                passed,
                "401 as expected (logout revokes session)"
                if passed
                else f"expected 401, got {after_logout.status_code}: {after_logout.text}",
            )


def run(base_url: str, role_checks: tuple[RoleCheck, ...]) -> list[CheckResult]:
    results: list[CheckResult] = []
    check_health_ready(base_url, results)
    for check in role_checks:
        check_role(base_url, check, results)
    return results


def print_summary(results: list[CheckResult]) -> bool:
    all_passed = True
    print()
    print("=" * 78)
    print("Gate 5 smoke test results")
    print("=" * 78)
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        if not result.passed:
            all_passed = False
        print(f"[{status}] {result.name} -- {result.detail}")
    print("=" * 78)
    passed_count = sum(1 for r in results if r.passed)
    print(f"{passed_count}/{len(results)} checks passed")
    print("=" * 78)
    return all_passed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"base URL of the running api_tender deployment (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--admin-username", default=DEFAULT_ROLE_CHECKS[0].username, help="username for the admin.users.read check"
    )
    parser.add_argument(
        "--admin-password", default=DEFAULT_ROLE_CHECKS[0].password, help="password for the admin.users.read check"
    )
    parser.add_argument(
        "--algorithm-username", default=DEFAULT_ROLE_CHECKS[1].username, help="username for the algorithm.policy.read check"
    )
    parser.add_argument(
        "--algorithm-password", default=DEFAULT_ROLE_CHECKS[1].password, help="password for the algorithm.policy.read check"
    )
    args = parser.parse_args()

    role_checks = (
        replace(DEFAULT_ROLE_CHECKS[0], username=args.admin_username, password=args.admin_password),
        replace(DEFAULT_ROLE_CHECKS[1], username=args.algorithm_username, password=args.algorithm_password),
    )

    results = run(args.base_url.rstrip("/"), role_checks)
    all_passed = print_summary(results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
