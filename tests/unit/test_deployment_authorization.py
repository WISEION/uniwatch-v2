from packages.platform.deployment_authorization import verify_digest_match, verify_distinct_approver


def test_verify_distinct_approver_accepts_different_identities():
    assert verify_distinct_approver("accessunico", "WISEION") is True


def test_verify_distinct_approver_rejects_same_identity():
    assert verify_distinct_approver("accessunico", "accessunico") is False


def test_verify_distinct_approver_is_case_sensitive():
    # A GitHub login is already canonical -- no normalization is invented here.
    assert verify_distinct_approver("accessunico", "AccessUnico") is True


def test_verify_digest_match_accepts_matching_commit():
    manifest = {"commit_sha": "abc123", "images": {"api_tender": "sha256:deadbeef"}}
    assert verify_digest_match(manifest, "abc123") is True


def test_verify_digest_match_rejects_mismatched_commit():
    manifest = {"commit_sha": "abc123", "images": {}}
    assert verify_digest_match(manifest, "different-commit") is False


def test_verify_digest_match_rejects_manifest_missing_commit_sha():
    manifest = {"images": {}}
    assert verify_digest_match(manifest, "abc123") is False
