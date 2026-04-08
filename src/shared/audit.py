"""Unified audit logger — writes to audit_log table.

Used throughout the system: scheduler daemon, supervisor daemon,
API endpoints, runner.py. Fire-and-forget async writes.

Usage:
    from shared.audit import log_audit

    await log_audit(
        session,
        entity_type="schedule",
        entity_id=schedule_id,
        action="triggered",
        summary="Lamudi daily incremental triggered by cron",
        actor="scheduler",
        is_automatic=True,
        tags=["cron", "incremental"],
    )
"""

from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models.audit_log import AuditLog
from shared.logging import get_logger

logger = get_logger("audit")


async def log_audit(
    session: AsyncSession,
    entity_type: str,
    action: str,
    summary: str,
    entity_id: str | None = None,
    actor: str = "system",
    is_automatic: bool = False,
    is_success: bool = True,
    diff: dict | None = None,
    tags: list[str] | None = None,
    metadata: dict | None = None,
) -> AuditLog:
    """Write an entry to the audit_log table.

    This is a fire-and-forget utility. If it fails, it logs a warning
    but never blocks the caller.
    """
    try:
        entry = AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor=actor,
            is_automatic=is_automatic,
            is_success=is_success,
            summary=summary,
            diff=diff,
            tags=tags,
            metadata_=metadata,
        )
        session.add(entry)
        await session.flush()
        logger.info(
            "audit.logged",
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            summary=summary,
        )
        return entry
    except Exception as exc:
        logger.warning("audit.write_failed", error=str(exc))
        raise
