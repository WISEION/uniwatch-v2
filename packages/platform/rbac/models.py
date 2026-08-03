"""FR-ADM-01..03: permissions are assigned to roles, roles to users; the
matrix is configuration (DB rows), not code."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Identity:
    subject: str
    role: str
    permissions: frozenset[str]

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions
