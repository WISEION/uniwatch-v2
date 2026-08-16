"""Local-auth login-attempt outcome (Phase 6, task 6.A). A distinct type
from `rbac.models.Identity` -- an Identity is "who you are once
authenticated"; a LoginOutcome is "what happened when you tried," which the
API layer maps to a status code without re-deriving lockout/credential
logic at the route boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from packages.platform.rbac.models import Identity

LoginStatus = Literal["success", "invalid_credentials", "account_locked"]


@dataclass(frozen=True)
class LoginOutcome:
    status: LoginStatus
    identity: Identity | None = None
    session_token: str | None = None
