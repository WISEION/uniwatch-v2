"""Local-auth password hashing (Phase 6, task 6.A, D-IDP). argon2-cffi's
`PasswordHasher` is memory-hard and purpose-built for this -- not a
hand-rolled PBKDF2/HMAC scheme.

`verify_password` never raises past this boundary: a malformed hash, a wrong
password, or any other argon2 verification failure is all "not verified,"
distinguished from a resolved identity the same deny-by-default way
`rbac/store.py::resolve_identity` already treats an unknown/disabled user."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if password_hash is None:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False
