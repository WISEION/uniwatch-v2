"""Pilot feedback queue (Phase 6, task 6.D, master plan section18 Phase 6's
"training materials and feedback queue for pilot users" result). A
submission is never edited or deleted -- only its triage status moves
open -> resolved, appending resolved_by/resolved_at/resolution_note rather
than mutating the original message, same discipline as exception_queue's
status lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

_COLUMNS = """id, submitted_by, category, message, status, resolution_note,
              resolved_by, correlation_id, submitted_at, resolved_at"""


@dataclass(frozen=True)
class PilotFeedback:
    id: int
    submitted_by: str
    category: str
    message: str
    status: str
    resolution_note: str | None
    resolved_by: str | None
    correlation_id: str
    submitted_at: datetime
    resolved_at: datetime | None


def _row_to_feedback(row) -> PilotFeedback:
    return PilotFeedback(
        id=row["id"],
        submitted_by=row["submitted_by"],
        category=row["category"],
        message=row["message"],
        status=row["status"],
        resolution_note=row["resolution_note"],
        resolved_by=row["resolved_by"],
        correlation_id=row["correlation_id"],
        submitted_at=row["submitted_at"],
        resolved_at=row["resolved_at"],
    )


async def submit_feedback(
    conn: AsyncConnection,
    *,
    submitted_by: str,
    category: str,
    message: str,
    correlation_id: str,
) -> PilotFeedback:
    row = (
        (
            await conn.execute(
                text(
                    f"""
                    INSERT INTO pilot_feedback (submitted_by, category, message, correlation_id)
                    VALUES (:submitted_by, :category, :message, :correlation_id)
                    RETURNING {_COLUMNS}
                    """
                ),
                {
                    "submitted_by": submitted_by,
                    "category": category,
                    "message": message,
                    "correlation_id": correlation_id,
                },
            )
        )
        .mappings()
        .one()
    )
    return _row_to_feedback(row)


async def list_feedback(conn: AsyncConnection, *, status: str | None = None) -> list[PilotFeedback]:
    if status is None:
        rows = (
            (await conn.execute(text(f"SELECT {_COLUMNS} FROM pilot_feedback ORDER BY submitted_at DESC, id DESC")))
            .mappings()
            .all()
        )
    else:
        rows = (
            (
                await conn.execute(
                    text(f"SELECT {_COLUMNS} FROM pilot_feedback WHERE status = :status ORDER BY submitted_at DESC, id DESC"),
                    {"status": status},
                )
            )
            .mappings()
            .all()
        )
    return [_row_to_feedback(row) for row in rows]


class FeedbackNotFound(Exception):
    pass


async def resolve_feedback(
    conn: AsyncConnection,
    *,
    feedback_id: int,
    resolved_by: str,
    resolution_note: str,
) -> PilotFeedback:
    row = (
        (
            await conn.execute(
                text(
                    f"""
                    UPDATE pilot_feedback
                    SET status = 'resolved', resolved_by = :resolved_by,
                        resolution_note = :resolution_note, resolved_at = now()
                    WHERE id = :id
                    RETURNING {_COLUMNS}
                    """
                ),
                {"id": feedback_id, "resolved_by": resolved_by, "resolution_note": resolution_note},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise FeedbackNotFound(f"pilot_feedback {feedback_id} not found")
    return _row_to_feedback(row)
