from packages.platform.auth.password_hashing import hash_password, verify_password


def test_verify_password_accepts_the_correct_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_password_rejects_a_wrong_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_verify_password_rejects_none_hash_without_raising():
    assert verify_password("anything", None) is False


def test_verify_password_rejects_malformed_hash_without_raising():
    assert verify_password("anything", "not-a-real-argon2-hash") is False


def test_hash_password_is_salted_and_not_reproducible_byte_for_byte():
    first = hash_password("same password")
    second = hash_password("same password")
    assert first != second
    assert verify_password("same password", first) is True
    assert verify_password("same password", second) is True
