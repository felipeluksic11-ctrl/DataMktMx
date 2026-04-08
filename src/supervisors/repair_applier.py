"""Repair Applier — safely applies selector overrides to DB.

Strategy: selector overrides stored in portals.selector_overrides (JSONB),
NOT by editing Python config files. Scrapers merge DB overrides on top of
static config.SELECTORS at initialization time.

Rollback: clear the override in the DB.
"""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.audit import log_audit
from shared.db.models import Portal
from shared.logging import get_logger

logger = get_logger("supervisor.repair_applier")


async def apply_selector_override(
    session: AsyncSession,
    portal_id: str,
    field: str,
    new_selector: str,
    actor: str = "auto",
) -> bool:
    """Apply a single selector override to the portal.

    Args:
        session: DB session
        portal_id: Portal UUID
        field: Field name (e.g., "price", "bedrooms")
        new_selector: New CSS selector value
        actor: "auto" for auto-applied, "admin" for manual

    Returns:
        True if applied successfully
    """
    try:
        stmt = select(Portal).where(Portal.id == portal_id)
        result = await session.execute(stmt)
        portal = result.scalar_one_or_none()

        if not portal:
            logger.warning("repair_applier.portal_not_found", portal_id=portal_id)
            return False

        # Merge override
        overrides = dict(portal.selector_overrides or {})
        old_value = overrides.get(field)
        overrides[field] = new_selector

        # Update portal
        portal.selector_overrides = overrides
        await session.flush()

        # Audit log
        await log_audit(
            session,
            entity_type="repair",
            entity_id=portal_id,
            action="applied",
            summary=f"Selector override for '{field}' on {portal.slug}: {new_selector}",
            actor=f"supervisor_{actor}",
            is_automatic=actor == "auto",
            diff={field: {"old": old_value, "new": new_selector}},
            tags=["repair", "selector", actor],
        )

        logger.info(
            "repair_applier.applied",
            portal=portal.slug,
            field=field,
            new_selector=new_selector,
            actor=actor,
        )
        return True

    except Exception:
        logger.exception("repair_applier.error", portal_id=portal_id, field=field)
        return False


async def rollback_selector_override(
    session: AsyncSession,
    portal_id: str,
    field: str,
) -> bool:
    """Remove a selector override, reverting to config.py baseline."""
    try:
        stmt = select(Portal).where(Portal.id == portal_id)
        result = await session.execute(stmt)
        portal = result.scalar_one_or_none()

        if not portal:
            return False

        overrides = dict(portal.selector_overrides or {})
        old_value = overrides.pop(field, None)

        if old_value is None:
            return False  # Nothing to rollback

        portal.selector_overrides = overrides
        await session.flush()

        await log_audit(
            session,
            entity_type="repair",
            entity_id=portal_id,
            action="rolled_back",
            summary=f"Selector override for '{field}' on {portal.slug} rolled back",
            actor="admin",
            diff={field: {"old": old_value, "new": None}},
            tags=["repair", "rollback"],
        )

        logger.info("repair_applier.rolled_back", portal=portal.slug, field=field)
        return True

    except Exception:
        logger.exception("repair_applier.rollback_error", portal_id=portal_id, field=field)
        return False
